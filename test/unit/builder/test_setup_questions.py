"""Asking for what a build cannot work out, before it plans around a guess.

A Stripe secret, a Cloudinary cloud name, whether the payments are real ones:
none of it is in the repository, and a plan written without knowing which
provider it is for is a plan for the wrong application. So the question comes
first, its answer goes into the plan, and the value goes to .env.local and
nowhere else.
"""
from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from test import _support  # noqa: F401
from builder_agent import setup
from builder_agent.errors import ToolError
from builder_agent.skills import SKILL_ROOT, read_manifest, select
from builder_agent.tools import build_registry
from builder_agent.tools.base import ToolContext


class DeclaredQuestionTests(unittest.TestCase):
    """The questions belong to the skills, so nothing here is enumerated."""

    def setUp(self):
        self.entries = read_manifest()

    def asked(self, request: str) -> list[str]:
        skills = select(self.entries, "", request, "nextjs-mongo")
        return [q["purpose"] for q in setup.questions_for(skills)]

    def test_a_request_is_only_asked_about_what_it_mentions(self):
        self.assertEqual(self.asked("a simple todo list"), [])
        self.assertIn("Payments", self.asked("a shop that takes card payments"))
        self.assertIn("Picture uploads", self.asked("a gallery where members upload photos"))
        self.assertIn("Email and SMS", self.asked("a booking app that emails a confirmation"))

    def test_a_request_that_rules_it_out_is_not_asked(self):
        self.assertNotIn("Payments", self.asked("a plant nursery, no payments"))

    def test_every_declaration_that_ships_is_usable(self):
        broken = [q for q in setup.questions_for(sorted(self.entries)) if q.get("error")]
        self.assertEqual(broken, [])

    def test_every_field_that_ships_carries_an_example(self):
        """Told only "API key", people paste an account id."""
        for question in setup.questions_for(sorted(self.entries)):
            for field in setup.all_fields(question):
                with self.subTest(field=field["key"]):
                    self.assertTrue(field["example"].strip())
                    self.assertTrue(field["label"].strip())

    def test_each_option_asks_only_for_its_own_settings(self):
        question = setup.questions_for(["payments"])[0]
        stripe = setup.fields_of(question, "stripe-test")
        payhere = setup.fields_of(question, "payhere-sandbox")
        self.assertTrue(any(f["key"].startswith("STRIPE_") for f in stripe))
        self.assertFalse(any(f["key"].startswith("PAYHERE_") for f in stripe))
        self.assertTrue(any(f["key"].startswith("PAYHERE_") for f in payhere))
        self.assertFalse(any(f["key"].startswith("STRIPE_") for f in payhere))

    def test_a_skill_with_nothing_to_ask_asks_nothing(self):
        self.assertEqual(setup.questions_for(["vitest", "react"]), [])

    def test_a_broken_declaration_stops_its_question_not_the_build(self):
        with tempfile.TemporaryDirectory() as folder:
            skill = Path(folder) / "broken"
            skill.mkdir()
            (skill / "setup.json").write_text('{"purpose": "Broken", "fields": [{"key": "x"}]}',
                                              encoding="utf-8")
            with unittest.mock.patch.object(setup, "SKILL_ROOT", Path(folder)):
                out = setup.questions_for(["broken"])
        self.assertEqual(len(out), 1)
        self.assertIn("error", out[0])


class AppliedAnswerTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / ".env.local").write_text("MONGODB_URI=mongodb://localhost/shop\n",
                                              encoding="utf-8")
        self.question = setup.questions_for(["payments"])[0]

    def env(self, name):
        return (self.root / name).read_text(encoding="utf-8")

    def test_what_was_supplied_is_written_and_the_rest_is_left_alone(self):
        setup.apply_answer(self.root, self.question, {
            "decision": "save", "choice": "payhere-sandbox",
            "values": {"PAYHERE_MERCHANT_ID": "1221149",
                       "PAYHERE_MERCHANT_SECRET": "a-real-secret",
                       "PAYHERE_SANDBOX": "true"}})
        body = self.env(".env.local")
        self.assertIn("MONGODB_URI=mongodb://localhost/shop", body)
        self.assertIn("PAYHERE_MERCHANT_ID=1221149", body)

    def test_the_other_option_is_never_written(self):
        setup.apply_answer(self.root, self.question, {
            "decision": "save", "choice": "payhere-sandbox",
            "values": {"PAYHERE_MERCHANT_ID": "1221149",
                       "STRIPE_SECRET_KEY": "sk_test_not_asked_for"}})
        self.assertNotIn("STRIPE", self.env(".env.local"))

    def test_no_value_reaches_the_note_the_plan_carries(self):
        applied = setup.apply_answer(self.root, self.question, {
            "decision": "save", "choice": "stripe-test",
            "values": {"STRIPE_SECRET_KEY": "sk_test_THE_ACTUAL_SECRET",
                       "STRIPE_PUBLISHABLE_KEY": "pk_test_1"}})
        self.assertNotIn("THE_ACTUAL_SECRET", applied["note"])
        self.assertIn("STRIPE_SECRET_KEY", applied["note"])
        self.assertIn("Stripe", applied["note"])

    def test_the_example_file_is_written_whether_or_not_anyone_answered(self):
        applied = setup.apply_answer(self.root, self.question, {"decision": "later",
                                                                "choice": "stripe-test"})
        self.assertIn("STRIPE_SECRET_KEY=sk_test_", self.env(".env.example"))
        self.assertFalse((self.root / ".env.local").read_text(encoding="utf-8")
                         .count("STRIPE"))
        self.assertIn("Not supplied", applied["note"])

    def test_a_value_cannot_smuggle_a_second_setting_in_on_a_new_line(self):
        """A newline inside a value would otherwise become a setting of its own."""
        setup.apply_answer(self.root, self.question, {
            "decision": "save", "choice": "stripe-test",
            "values": {"STRIPE_SECRET_KEY": "sk_test_1\nADMIN_OVERRIDE=yes"}})
        names = [line.split("=", 1)[0] for line in self.env(".env.local").splitlines() if line]
        self.assertEqual(names, ["MONGODB_URI", "STRIPE_SECRET_KEY"])

    def test_answering_twice_updates_rather_than_appends(self):
        for value in ("sk_test_first", "sk_test_second"):
            setup.apply_answer(self.root, self.question, {
                "decision": "save", "choice": "stripe-test",
                "values": {"STRIPE_SECRET_KEY": value}})
        body = self.env(".env.local")
        self.assertEqual(body.count("STRIPE_SECRET_KEY="), 1)
        self.assertIn("sk_test_second", body)


class FieldValidationTests(unittest.TestCase):
    def test_a_field_without_an_example_is_refused(self):
        with self.assertRaises(ToolError):
            setup.read_fields([{"key": "API_KEY", "label": "Key"}])

    def test_a_key_that_is_not_an_environment_variable_is_refused(self):
        for key in ("api key", "9LEADING", "", "A", "KEY-WITH-DASH"):
            with self.subTest(key=key), self.assertRaises(ToolError):
                setup.read_fields([{"key": key, "example": "x"}])

    def test_a_name_written_in_lower_case_is_corrected_rather_than_refused(self):
        """The name is what it becomes in the file, not a spelling test."""
        [field] = setup.read_fields([{"key": "stripe_secret_key", "example": "sk_test_1"}])
        self.assertEqual(field["key"], "STRIPE_SECRET_KEY")

    def test_the_same_setting_cannot_be_asked_for_twice(self):
        with self.assertRaises(ToolError):
            setup.read_fields([{"key": "API_KEY", "example": "a"},
                               {"key": "API_KEY", "example": "b"}])


class AskingToolTests(unittest.TestCase):
    """The two ways a run can ask something once it is already going."""

    def setUp(self):
        from builder_agent.events import Events
        from builder_agent.sandbox import Sandbox
        self.root = Path(tempfile.mkdtemp())
        self.events = Events()
        self.registry = build_registry()
        self.context = ToolContext(sandbox=Sandbox(self.root), config=None,
                                   events=self.events, memory=None, processes=None,
                                   approvals=None)

    def call(self, name, args):
        tool = self.registry.get(name)
        return tool.handler(self.registry.validate(name, args), self.context)

    def test_a_question_nobody_answers_returns_the_assumption(self):
        out = self.call("askUser", {
            "question": "Can a member cancel a booking after it has started?",
            "assumption": "allow cancellation up to one hour before"})
        self.assertTrue(out["ok"])
        self.assertIn("one hour before", out["content"])
        self.assertIn("do not ask this again", out["content"])

    def test_settings_nobody_supplies_still_leave_the_names_behind(self):
        out = self.call("askForSetup", {
            "purpose": "Email notifications through Resend",
            "fields": [{"key": "RESEND_API_KEY", "label": "API key",
                        "example": "re_123abc"}]})
        self.assertTrue(out["ok"])
        self.assertIn("RESEND_API_KEY=re_123abc",
                      (self.root / ".env.example").read_text(encoding="utf-8"))
        self.assertFalse((self.root / ".env.local").exists())

    def test_neither_tool_can_be_called_without_saying_what_it_is_for(self):
        with self.assertRaises(ToolError):
            self.call("askUser", {"question": "eh?"})
        with self.assertRaises(ToolError):
            self.call("askForSetup", {"purpose": "keys",
                                      "fields": [{"key": "A_KEY", "example": "x"}]})

    def test_a_run_may_only_stop_to_ask_so_many_times(self):
        """A model with no budget turns a build into an interview."""
        from builder_agent.approvals import Approvals
        from builder_agent.tools.setup import MAX_QUESTIONS
        self.context.approvals = Approvals(self.events, enabled=False)
        for number in range(MAX_QUESTIONS):
            out = self.call("askUser", {"question": f"Which reading of requirement {number}?",
                                        "assumption": "the narrower one"})
            self.assertTrue(out["ok"])
        with self.assertRaises(ToolError) as refused:
            self.call("askUser", {"question": "And one more thing entirely?"})
        self.assertIn("budget", str(refused.exception))

    def test_the_budget_holds_even_where_nobody_can_answer(self):
        """A CLI run resolves every question to its default; that is not a licence."""
        from builder_agent.approvals import Approvals
        approvals = Approvals(self.events, enabled=False)
        for _ in range(3):
            approvals.ask("question", {"question": "?"}, {"decision": "default"})
        self.assertEqual(approvals.asked("question"), 3)
        self.assertEqual(approvals.asked("setup"), 0)


class DesignerToolTests(unittest.TestCase):
    """What the prototype agent is allowed to reach for."""

    def test_the_prototype_agent_can_ask_rather_than_guess(self):
        """A drawing is where an ambiguity is cheapest to settle, so it may ask."""
        source = (Path(__file__).resolve().parents[3]
                  / "builder-agent" / "builder_agent" / "designer.py"
                  ).read_text(encoding="utf-8")
        self.assertIn('"askUser"', source)


class SkillFileTests(unittest.TestCase):
    """Each provider's detail is its own file, so only the chosen one is read.

    Derived from the skills rather than listed here. The list version covered
    three skills and silently ignored every one added afterwards, which is how
    a skill came to tell the model to read four pages that did not exist.
    """

    # `readSkill("maps", "mapbox.md")` and `resourcePath="mapbox.md"` both.
    NAMES = re.compile(r'resourcePath="([^"]+\.md)"'
                       r"|readSkill\(\s*[\"']([^\"']+)[\"']\s*,\s*[\"']([^\"']+\.md)[\"']")

    def skills(self):
        """Every bundled skill that has a page of its own."""
        return sorted(d.name for d in SKILL_ROOT.iterdir()
                      if d.is_dir() and (d / "SKILL.md").is_file())

    def named_by(self, skill):
        """The files a skill tells the model it can read."""
        body = (SKILL_ROOT / skill / "SKILL.md").read_text(encoding="utf-8")
        found = set()
        for direct, _owner, referenced in self.NAMES.findall(body):
            name = direct or referenced
            # `<entry>.md` in an index is a placeholder, not a file.
            if name and "<" not in name:
                found.add(name)
        return found

    def test_every_provider_named_by_a_skill_has_a_file_to_read(self):
        for skill in self.skills():
            for name in sorted(self.named_by(skill)):
                with self.subTest(skill=skill, file=name):
                    self.assertTrue((SKILL_ROOT / skill / name).is_file(),
                                    f"{skill}/SKILL.md sends the model to {name}, "
                                    "which is not there")

    def test_a_declared_option_matches_a_file_the_skill_points_at(self):
        """The question and the guidance cannot drift apart silently.

        Every option that asks for credentials is a provider somebody will
        build against, so the skill has to have something to say about it.
        `none`, `local` and `log-only` ask for nothing and need no page.
        """
        for skill in self.skills():
            declaration = SKILL_ROOT / skill / "setup.json"
            if not declaration.is_file():
                continue
            pages = self.named_by(skill)
            for option in json.loads(declaration.read_text(encoding="utf-8"))["choices"]:
                if not option.get("fields"):
                    continue
                with self.subTest(skill=skill, provider=option["id"]):
                    stem = option["id"].split("-")[0]
                    self.assertTrue(
                        any(stem in page for page in pages),
                        f"{skill} offers {option['id']} and its SKILL.md names no "
                        f"page about it; it has {sorted(pages)}")


if __name__ == "__main__":
    unittest.main()


class ChosenOptionTests(unittest.TestCase):
    """What an option needs is what gets written, and nothing else.

    Caught by running a real build: choosing "send nothing" wrote Resend's and
    Twilio's keys into the example file of a project whose author had just said
    they did not want to send anything.
    """

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.question = setup.questions_for(["notifications"])[0]

    def test_an_option_that_needs_nothing_writes_nothing(self):
        setup.apply_answer(self.root, self.question,
                           {"decision": "save", "choice": "log-only"})
        self.assertFalse((self.root / ".env.example").exists()
                         and (self.root / ".env.example").read_text(encoding="utf-8").strip())

    def test_an_option_that_needs_something_writes_only_its_own(self):
        setup.apply_answer(self.root, self.question,
                           {"decision": "save", "choice": "resend-sandbox",
                            "values": {"RESEND_API_KEY": "re_fake"}})
        body = (self.root / ".env.example").read_text(encoding="utf-8")
        self.assertIn("RESEND_API_KEY", body)
        self.assertNotIn("TWILIO", body)

    def test_a_question_nobody_answered_records_every_name_it_could_have_used(self):
        """No choice at all is the one case where the whole list is the answer."""
        setup.apply_answer(self.root, self.question, {"decision": "later"})
        body = (self.root / ".env.example").read_text(encoding="utf-8")
        self.assertIn("RESEND_API_KEY", body)
        self.assertIn("TWILIO_ACCOUNT_SID", body)
