"""The loop, driven by a scripted model.

No network and no real model: the router is replaced by a list of turns, which
makes the loop's own decisions the thing under test. What matters is that it
executes tool calls in order, feeds failures back as observations, refuses to
finish without evidence, and stops repeating an action that cannot work.
"""
from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from test import _support  # noqa: F401
from qa_agent.browser import Browser
from qa_agent.evidence import Evidence, failure_packet
from qa_agent.tools import build_registry as build_qa_registry
from builder_agent.config import Config
from builder_agent.events import Events
from builder_agent.llm import Reply, ToolCall
from builder_agent.loop import Loop
from builder_agent.memory import Memory
from builder_agent.processes import Processes
from builder_agent.sandbox import Sandbox


class ScriptedRouter:
    """Replays a fixed list of turns, and records what it was asked."""

    def __init__(self, turns):
        self.turns = list(turns)
        self.requests = []
        self.usage = {"prompt": 0, "completion": 0, "requests": 0}
        self.label = "scripted/model"
        self.model = "scripted"

    def ask(self, messages, tools=None, **kwargs):
        self.requests.append({"messages": messages, "tools": tools})
        if not self.turns:
            # A test that runs off the end of its script has stopped testing
            # what it meant to; say so instead of looping.
            raise AssertionError("the scripted model ran out of turns")
        return self.turns.pop(0)

    @staticmethod
    def context_window():
        return 0


def call(tool, **args):
    return ToolCall(f"c{abs(hash((tool, tuple(sorted(args)))))%9999}", tool, args)


def turn(*calls, content=""):
    return Reply(content=content, calls=list(calls))


class LoopTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.events = Events()
        self.seen = []
        self.events.any(lambda event, payload: self.seen.append(event))

    def build(self, turns, **overrides):
        verification_kinds = overrides.pop("verification_kinds", None)
        config = Config(workspace=self.root, model="scripted",
                        state_root=self.root / ".state", **overrides)
        self.router = ScriptedRouter(turns)
        return Loop(config=config, registry=build_qa_registry(), router=self.router,
                    memory=Memory(evidence=Evidence()), sandbox=Sandbox(self.root), events=self.events,
                    processes=Processes(self.events), browser=Browser(self.events),
                    verification_kinds=verification_kinds, failure_packet=failure_packet)

    # -- executing -------------------------------------------------------
    def test_follow_up_receives_the_previous_final_answer(self):
        suggestion = "Use either 'Browse meals' or 'Find your next meal' for the landing button."
        loop = self.build([turn(content=suggestion), turn(content="Updated the button.")])
        loop.testing_enabled = False  # This conversation does not run application tests.

        loop.run("Suggest two labels for the landing page button")
        saved = loop.memory.serialize()
        loop.memory.restore(saved)  # The same transcript must also survive persistence.
        loop.run("Use the second label you suggested")

        messages = self.router.requests[1]["messages"]
        self.assertTrue(any(message["role"] == "assistant"
                            and message.get("content") == suggestion for message in messages),
                        "the follow-up provider request lost the assistant's final answer")

    def test_unit_stage_can_finish_without_launching_unassigned_browser_and_runtime_work(self):
        loop = self.build([], verification_kinds=("unit",))
        evidence = loop.memory.evidence
        evidence.define_scope("web", "nextjs-mongo", [
            {"id": "validation", "description": "reject invalid inputs", "evidence": ["unit"]}])
        self.assertTrue(loop._completion_block())
        record = evidence.start("unit", "validation", "vitest run --coverage", [], ["validation"])
        evidence.observe(record, {"exitCode": 0, "coverage": {
            kind: {"pct": 100} for kind in ("lines", "statements", "functions", "branches")}})
        self.assertEqual(loop._completion_block(), "")
        self.assertEqual(evidence.required_kinds, ["unit"])

    def test_read_only_terminal_observation_keeps_current_test_evidence(self):
        loop = self.build([])
        record = loop.memory.evidence.start(
            kind="unit", suite="books", command="npm test", test_files=[], covers=[])
        loop.memory.evidence.observe(record, {"exitCode": 0, "stdout": "passed", "stderr": ""})
        revision = loop.memory.evidence.revision
        with patch.object(loop.processes, "run", return_value={
            "exitCode": 0, "elapsed": 0.1, "stdout": "v24.19.0", "stderr": ""}) as command:
            result = loop._run_one(call("executeTerminal", command="node --version", changesProject=False))
            command.assert_called_once()
            self.assertTrue(result["ok"])
        self.assertEqual(loop.memory.evidence.revision, revision)
        self.assertEqual(record["revision"], loop.memory.evidence.revision)

    def test_project_changing_command_invalidates_evidence_once(self):
        loop = self.build([])
        revision = loop.memory.evidence.revision
        with patch.object(loop.processes, "run", return_value={
            "exitCode": 0, "elapsed": 0.1, "stdout": "installed", "stderr": ""}) as command:
            result = loop._run_one(call("executeTerminal", command="npm install", changesProject=True))
            command.assert_called_once()
            self.assertTrue(result["ok"])
        self.assertEqual(loop.memory.evidence.revision, revision + 1)

    def test_tool_calls_in_one_turn_run_in_order_and_all_report_back(self):
        loop = self.build([
            turn(call("writeFile", filePath="a.js", content="one"),
                 call("writeFile", filePath="b.js", content="two")),
            turn(content="done"),
        ], unit_tests=False, e2e_tests=False)
        loop.testing_enabled = False        # this test is about execution order

        outcome = loop.run("write two files")

        self.assertEqual(outcome.status, "completed")
        self.assertEqual((self.root / "a.js").read_text(), "one")
        self.assertEqual((self.root / "b.js").read_text(), "two")
        self.assertEqual(outcome.tool_calls, 2)
        self.assertIn("tool:start", self.seen)

    def test_a_failed_tool_becomes_an_observation_the_model_can_act_on(self):
        loop = self.build([
            turn(call("readFile", filePath="missing.js")),
            turn(content="the file was not there"),
        ])
        loop.testing_enabled = False

        outcome = loop.run("read a file")

        self.assertEqual(outcome.status, "completed")
        results = [m for m in loop.memory.messages if m["role"] == "tool"]
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0]["meta"]["ok"])
        self.assertIn("No such file", results[0]["content"])

    def test_an_unknown_tool_is_answered_with_the_tools_that_do_exist(self):
        loop = self.build([turn(call("summonPony", colour="pink")),
                           turn(content="understood")])
        loop.testing_enabled = False

        loop.run("do something impossible")

        result = [m for m in loop.memory.messages if m["role"] == "tool"][0]
        self.assertIn('no tool named "summonPony"', result["content"])
        self.assertIn("readFile", result["content"])
        self.assertIn("Did you mean", result["content"])

    def test_a_reply_with_neither_a_call_nor_an_answer_is_prompted_once_more(self):
        loop = self.build([turn(), turn(content="here is the answer")])
        loop.testing_enabled = False

        outcome = loop.run("say something")

        self.assertEqual(outcome.result, "here is the answer")
        self.assertEqual(len(self.router.requests), 2)

    # -- guards ----------------------------------------------------------
    def test_the_same_failing_action_is_stopped_rather_than_repeated_forever(self):
        repeat = [turn(call("readFile", filePath="missing.js")) for _ in range(6)]
        loop = self.build(repeat + [turn(content="I gave up on that file")])
        loop.testing_enabled = False

        loop.run("read a file that is not there")

        blocked = [m for m in loop.memory.messages if m["role"] == "tool"
                   and "already failed" in m["content"]]
        self.assertTrue(blocked, "an unchanged failing action must eventually be refused")

    def test_a_successful_write_unblocks_a_previously_failing_action(self):
        loop = self.build([
            turn(call("readFile", filePath="late.js")),
            turn(call("readFile", filePath="late.js")),
            turn(call("readFile", filePath="late.js")),
            turn(call("writeFile", filePath="late.js", content="now it exists")),
            turn(call("readFile", filePath="late.js")),
            turn(content="read it"),
        ])
        loop.testing_enabled = False

        loop.run("read a file that appears later")

        last = [m for m in loop.memory.messages if m["role"] == "tool"][-1]
        self.assertIn("now it exists", last["content"])

    def test_a_run_cannot_report_completion_without_verification_evidence(self):
        loop = self.build(
            [turn(call("writeFile", filePath="app.js", content="x"))]
            + [turn(content="All done, everything works.") for _ in range(8)])

        outcome = loop.run("build something")

        gate = [m for m in loop.memory.messages
                if m.get("meta", {}).get("kind") == "completion-gate"]
        self.assertTrue(gate, "a completion claim with no evidence must be refused")
        self.assertIn("defineVerificationScope", gate[0]["content"])
        # The gate sends the run back to work; it must not trap it there.
        self.assertEqual(outcome.status, "unverified")
        self.assertIn("Reported without the required evidence", outcome.result)

    def test_evidence_closes_the_gate_and_the_run_finishes(self):
        loop = self.build([
            turn(call("defineVerificationScope", projectType="web app",
                      stack="Next.js", requirements=[
                          {"id": "home", "description": "Home renders",
                           "evidence": ["runtime"]}])),
            turn(call("recordTestEvidence", kind="runtime", suite="smoke",
                      source="probe", status="passed", covers=["home"])),
            turn(content="Home renders; the runtime probe passed."),
        ], unit_tests=False, e2e_tests=False)

        outcome = loop.run("build and prove a home page")

        self.assertEqual(outcome.status, "completed")
        self.assertTrue(outcome.evidence["ready"])

    # -- context ---------------------------------------------------------
    def test_tool_schemas_are_trimmed_rather_than_letting_the_request_fail(self):
        loop = self.build([turn(content="ok")])
        loop.budget.limit = 6000

        excluded = loop._fit_tools()

        self.assertIn("browserSnapshot", excluded)
        self.assertNotIn("writeFile", excluded)
        self.assertNotIn("runTests", excluded)

    def test_a_large_window_keeps_every_tool(self):
        loop = self.build([turn(content="ok")])
        loop.budget.limit = 128_000

        excluded = loop._fit_tools()

        self.assertEqual(set(excluded), {"recallCompactedContext"})

    def test_the_pinned_frame_carries_the_stack_layout_and_skills(self):
        loop = self.build([turn(content="ok")])
        loop.testing_enabled = False

        loop.run("build a hotel booking app")

        kinds = {m.get("meta", {}).get("kind") for m in loop.memory.messages}
        self.assertIn("project-layout", kinds)
        self.assertIn("skill-catalog", kinds)
        self.assertIn("task", kinds)
        self.assertTrue((self.root / ".agents" / "skills" / "stack-nextjs").is_dir())

    def test_an_empty_workspace_is_scaffolded_from_the_verified_template(self):
        loop = self.build([turn(content="ok")])
        loop.testing_enabled = False

        loop.run("build a hotel booking app")

        self.assertTrue((self.root / "package.json").is_file())
        self.assertTrue((self.root / "vitest.config.js").is_file())
        kinds = {m.get("meta", {}).get("kind") for m in loop.memory.messages}
        self.assertIn("scaffold", kinds)

    def test_a_workspace_that_already_has_a_project_is_left_alone(self):
        (self.root / "package.json").write_text('{"name":"mine"}', encoding="utf-8")
        loop = self.build([turn(content="ok")])
        loop.testing_enabled = False

        loop.run("add a page")

        self.assertEqual((self.root / "package.json").read_text(), '{"name":"mine"}')

    def test_cancelling_ends_the_run_without_reporting_a_failure(self):
        loop = self.build([turn(call("writeFile", filePath="a.js", content="x")),
                           turn(content="done")])
        loop.testing_enabled = False
        loop.cancel = lambda: True

        outcome = loop.run("build something")

        self.assertEqual(outcome.status, "cancelled")
        self.assertIn("agent:abort", self.seen)


if __name__ == "__main__":
    unittest.main()


class RepeatedReadTests(unittest.TestCase):
    """A read that keeps returning the same answer is not progress.

    Watched a drawing pass read one skill sixteen times in ninety seconds and
    write nothing. Every call succeeded, so the repeat-failure guard never saw
    it, and nothing else was in a position to notice.
    """

    def loop(self):
        from builder_agent.config import Config
        from builder_agent.events import Events
        from builder_agent.memory import Memory
        from builder_agent.sandbox import Sandbox
        from builder_agent.tools import build_registry
        from builder_agent.llm import Reply

        root = Path(tempfile.mkdtemp())
        (root / "notes.md").write_text("the same answer every time", encoding="utf-8")

        class Router:
            label = "scripted/model"
            model = "scripted"
            usage = {"prompt": 0, "completion": 0, "requests": 0}

            def ask(self, messages, tools=None, **kwargs):
                return Reply(content="done")

            @staticmethod
            def context_window():
                return 0

        return Loop(config=Config(workspace=root, model="scripted", unit_tests=False,
                                  e2e_tests=False, state_root=root / ".state"),
                    registry=build_registry(), router=Router(),
                    memory=Memory(budget_tokens=64_000), sandbox=Sandbox(root),
                    events=Events(), processes=None, browser=None)

    def read(self, loop, name="notes.md", **window):
        from builder_agent.llm import ToolCall
        loop._run_one(ToolCall("c", "readFile", {"filePath": name, **window}))
        return loop.memory.messages[-1].get("content") or ""

    def test_the_same_answer_three_times_is_noticed_but_never_refused(self):
        loop = self.loop()
        first = self.read(loop)
        second = self.read(loop)
        third = self.read(loop)

        self.assertNotIn("Read 2 times", first)
        self.assertNotIn("Read 2 times", second)
        self.assertIn("Read 3 times in this run", third)
        # The answer itself is still there — this is an observation, not a
        # refusal, and the model may well still need what it read.
        self.assertIn("the same answer every time", third)

    def test_reading_the_same_file_many_times_is_still_allowed(self):
        """Nothing refuses a repeat. The model decides whether it needs it.

        The guard this replaces turned the sixth read into a failure, which is
        a gate: it answers a question only the model can answer, and it answers
        it wrong whenever the file is genuinely needed again.
        """
        loop = self.loop()
        for _ in range(8):
            body = self.read(loop)
        self.assertIs(loop.memory.messages[-1]["meta"]["ok"], True)
        self.assertIn("the same answer every time", body)

    def test_a_window_of_a_file_already_read_is_still_that_file(self):
        """Paging must not buy a fresh count for every offset.

        `_signature` hashes offset and limit with the path, so nine slices of
        one stylesheet looked like nine unrelated calls: a build read
        styles.css forty-nine times, wrote nothing, and ran twelve minutes.
        """
        loop = self.loop()
        long = "\n".join(f"line {n}" for n in range(1, 40))
        (Path(loop.sandbox.root) / "long.md").write_text(long, encoding="utf-8")

        self.read(loop, "long.md", offset=0, limit=10)
        self.read(loop, "long.md", offset=10, limit=10)
        third = self.read(loop, "long.md", offset=11, limit=10)

        self.assertIn("Read 3 times in this run", third)
        self.assertIn("long.md", third)

    def test_a_different_file_starts_its_own_count(self):
        loop = self.loop()
        (Path(loop.sandbox.root) / "other.md").write_text("different", encoding="utf-8")
        for _ in range(3):
            self.read(loop)
        other = self.read(loop, "other.md")
        self.assertNotIn("Read 2 times", other)

    def test_changing_the_project_clears_the_count(self):
        """After an edit the same read is a new question, not a repeat."""
        loop = self.loop()
        for _ in range(3):
            self.read(loop)
        loop.repeated_reads.clear()          # what a mutating tool does
        self.assertNotIn("Read 2 times", self.read(loop))

    def edit(self, loop, name, old, new):
        from builder_agent.llm import ToolCall
        loop._run_one(ToolCall("e", "editFile",
                               {"filePath": name, "oldString": old, "newString": new}))
        return loop.memory.messages[-1]

    def test_editing_one_file_many_times_is_never_refused(self):
        """An edit fails when it is wrong, never because it is the fourth.

        A count that refuses the next edit is a gate: it decides for the model
        how many changes a file is allowed to need. What makes edits rare is
        the model keeping the file in its window, not the engine saying no.
        """
        loop = self.loop()
        page = "page.html"
        (Path(loop.sandbox.root) / page).write_text("a\nb\nc\nd\ne\nf\n", encoding="utf-8")

        for old, new in (("a", "A"), ("b", "B"), ("c", "C"), ("d", "D"), ("e", "E")):
            result = self.edit(loop, page, old, new)
            self.assertIs(result["meta"]["ok"], True, f"edit {old}->{new} was refused")

        self.assertEqual((Path(loop.sandbox.root) / page).read_text(encoding="utf-8"),
                         "A\nB\nC\nD\nE\nf\n")

    def test_an_edit_still_fails_when_it_is_actually_wrong(self):
        """The only refusals left are correctness ones."""
        loop = self.loop()
        page = "page.html"
        (Path(loop.sandbox.root) / page).write_text("one\ntwo\n", encoding="utf-8")
        missing = self.edit(loop, page, "nowhere-in-the-file", "x")
        self.assertIs(missing["meta"]["ok"], False)
