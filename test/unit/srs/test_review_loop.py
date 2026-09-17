"""The reviewer sends a weak draft back, and always stops.

Two things are worth proving here, because both are ways this could go wrong
quietly:

  * the loop can move backwards. `_checkpointed` used to be a `for` over a
    range, which could only ever go forwards; the reviewer's enhance edge is the
    one place that changes.
  * it always stops. The cap, the no-progress rule and an unavailable model each
    end the loop on their own, and none of them depends on the model agreeing to
    stop - a reviewer asked to judge its own judgement tends to accept.
"""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test import _support  # noqa: F401 - puts the agent packages on the path
from srs_agent.app.agents import reviewer
from srs_agent.app.agents.reviewer import _satisfied, _validator, review_srs_node
from srs_agent.app.graph import workflow
from srs_agent.app.services import storage as storage_module


SCORES = {"functional": 4, "non_functional": 4, "security": 4,
          "ambiguity": 4, "traceability": 4}


def document(ids=("FR-001", "FR-002")):
    return {"srs_document": {
        "project_name": "Library",
        "functional_requirements": [
            {"id": i, "module": "Loans", "requirement": f"The member shall {i}."} for i in ids],
        "non_functional_requirements": [{"id": "NFR-001", "category": "Performance",
                                         "requirement": "It shall be quick."}],
    }}


def run(coro):
    return asyncio.run(coro)


class Verdict(unittest.TestCase):
    def test_python_decides_not_the_model(self):
        """A model that says 'accept' while raising a blocker is not obeyed."""
        self.assertFalse(_satisfied({"verdict": "accept", "scores": SCORES,
                                     "findings": [{"severity": "blocker"}]}))
        self.assertTrue(_satisfied({"verdict": "revise", "scores": SCORES, "findings": []}))

    def test_a_low_score_blocks_without_a_named_requirement(self):
        weak = {**SCORES, "security": 1}
        self.assertFalse(_satisfied({"scores": weak, "findings": []}))

    def test_a_finding_against_an_unknown_requirement_is_rejected(self):
        check = _validator(document()["srs_document"])
        check({"scores": SCORES, "findings": [
            {"requirement_id": "FR-001", "severity": "major", "problem": "vague"}]})
        with self.assertRaises(ValueError):
            check({"scores": SCORES, "findings": [
                {"requirement_id": "FR-999", "severity": "major", "problem": "vague"}]})

    def test_a_bad_severity_is_rejected(self):
        check = _validator(document()["srs_document"])
        with self.assertRaises(ValueError):
            check({"scores": SCORES, "findings": [
                {"requirement_id": "FR-001", "severity": "catastrophic", "problem": "x"}]})


class Stops(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patcher = patch.object(reviewer.storage, "save_review_round",
                               lambda *a, **k: Path(self.tmp.name) / "round.json")
        patcher.start()
        self.addCleanup(patcher.stop)

    def _review(self, state, verdict=None, error=None):
        async def fake(**kwargs):
            if error:
                raise error
            return verdict

        class Fake:
            complete_json = staticmethod(fake)

        with patch.object(reviewer, "get_llm", lambda: Fake()), \
             patch.object(reviewer, "get_active_skills_guidance", lambda **k: "standards"):
            return run(review_srs_node(state))

    def base(self):
        return {"project_id": "p1", "srs": document()}

    def test_a_blocking_finding_sends_the_draft_back(self):
        out = self._review(self.base(), verdict={
            "scores": SCORES, "findings": [
                {"requirement_id": "FR-001", "severity": "blocker", "problem": "untestable"}]})
        self.assertEqual(out["_goto"], "generate_srs_node")
        self.assertEqual(out["review_round"], 1)
        self.assertEqual(out["review_blockers"], 1)

    def test_the_cap_ends_it(self):
        state = {**self.base(), "review_round": 2}      # settings default cap is 2
        out = self._review(state, verdict={
            "scores": SCORES, "findings": [
                {"requirement_id": "FR-001", "severity": "blocker", "problem": "untestable"}]})
        self.assertNotIn("_goto", out)
        self.assertEqual(
            out["srs"]["srs_document"]["requirements_quality_review"]["reviewer"]["status"],
            "capped")

    def test_no_progress_ends_it(self):
        state = {**self.base(), "review_round": 1, "review_blockers": 1}
        out = self._review(state, verdict={
            "scores": SCORES, "findings": [
                {"requirement_id": "FR-001", "severity": "blocker", "problem": "still untestable"}]})
        self.assertNotIn("_goto", out)
        self.assertEqual(
            out["srs"]["srs_document"]["requirements_quality_review"]["reviewer"]["status"],
            "stalled")

    def test_an_unavailable_model_accepts_the_draft(self):
        from srs_agent.app.llm import LLMUnavailable
        out = self._review(self.base(), error=LLMUnavailable("ollama is down"))
        self.assertNotIn("_goto", out)
        self.assertEqual(
            out["srs"]["srs_document"]["requirements_quality_review"]["reviewer"]["status"],
            "skipped")

    def test_the_verdict_lands_inside_an_existing_key(self):
        """A new top-level key would become a new section in app.md."""
        out = self._review(self.base(), verdict={"scores": SCORES, "findings": []})
        doc = out["srs"]["srs_document"]
        self.assertIn("reviewer", doc["requirements_quality_review"])
        self.assertNotIn("reviewer", doc)
        self.assertNotIn("review_feedback", doc)


class Loop(unittest.IsolatedAsyncioTestCase):
    async def test_a_step_can_send_the_run_back_to_an_earlier_one(self):
        seen = []

        async def first(state):
            seen.append("first")
            return {}

        async def second(state):
            seen.append("second")
            # Ask to go back exactly once.
            return {"_goto": "first"} if len(seen) < 3 else {}

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # `_checkpointed` imports storage inside the function, so the module is
        # what has to be patched, not an attribute of workflow.
        with patch.object(storage_module, "project_dir", lambda _pid: Path(tmp.name)):
            await workflow._checkpointed("t", {"project_id": "p1"}, [first, second])

        self.assertEqual(seen, ["first", "second", "first", "second"])

    async def test_goto_never_reaches_the_state(self):
        """`_goto` is a routing instruction, not a field of the document."""
        async def only(state):
            return {"_goto": "nowhere"}

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        with patch.object(storage_module, "project_dir", lambda _pid: Path(tmp.name)):
            out = await workflow._checkpointed("t", {"project_id": "p1"}, [only])

        self.assertNotIn("_goto", out)
        saved = json.loads((Path(tmp.name) / "t-checkpoint.json").read_text(encoding="utf-8"))
        self.assertNotIn("_goto", saved["state"])


if __name__ == "__main__":
    unittest.main()
