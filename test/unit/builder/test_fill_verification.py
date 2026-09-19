"""Typing into a control, and the proof that it happened.

`Input.insertText` goes wherever focus is. When the click before it misses,
the text goes nowhere and every signal the journey has still says the step
passed - so the run fails several steps later on an assertion about a URL,
with an empty form behind it that nothing in the report mentions.

That is not a hypothesis. One build spent forty minutes and fifteen identical
turns on it, then edited the product's login page twice to match a test whose
fields were never filled. What is tested here is that the same failure now
stops at the step that caused it, and that the evidence says which control was
empty - in text, because that is what reads it next.
"""
from __future__ import annotations

import unittest

from test import _support  # noqa: F401
from builder_agent import browser
from builder_agent.errors import ToolError
from builder_agent.journeys import form_state

FILLED = {"fillable": True, "value": "admin@indoora.com", "focused": True,
          "tag": "input", "type": "email", "label": "email"}


class FakeCdp:
    """Enough of the protocol for one control and one page."""

    def __init__(self, control=None, tree=(), url="http://localhost:5173/login"):
        self.control, self.tree, self.page_url = control, list(tree), url
        self.sent = []

    def on(self, *args, **kwargs):
        pass

    def post(self, *args, **kwargs):
        pass

    def send(self, method, params=None, session=None, timeout=None):
        self.sent.append((method, params or {}))
        if method == "DOM.getBoxModel":
            return {"model": {"content": [0, 0, 10, 0, 10, 10, 0, 10]}}
        if method == "DOM.resolveNode":
            return {"object": {"objectId": "node-1"}}
        if method == "Runtime.callFunctionOn":
            return {"result": {"value": self.control}}
        if method == "Accessibility.getFullAXTree":
            return {"nodes": self.tree}
        if method == "Runtime.evaluate":
            expression = (params or {}).get("expression", "")
            return {"result": {"value": self.page_url if "location.href" in expression else 1}}
        return {}


def page_with(control=None, tree=(), url="http://localhost:5173/login"):
    return browser.Page(FakeCdp(control, tree, url), "target-1", "session-1")


def ax(role, name="", value=None):
    node = {"role": {"value": role}, "name": {"value": name},
            "backendDOMNodeId": 1}
    if value is not None:
        node["value"] = {"value": value}
    return node


class FillReadBackTests(unittest.TestCase):
    def test_a_control_left_empty_fails_the_step_that_typed_into_it(self):
        page = page_with({**FILLED, "value": ""})
        with self.assertRaises(ToolError) as raised:
            page.fill(1, "admin@indoora.com")
        said = str(raised.exception)
        self.assertIn("E2E_FILL_FAILED", said)
        self.assertIn("email", said)
        self.assertIn("admin@indoora.com", said)

    def test_a_control_that_never_took_focus_fails_and_says_the_click_missed(self):
        page = page_with({**FILLED, "focused": False})
        with self.assertRaises(ToolError) as raised:
            page.fill(1, "admin@indoora.com")
        self.assertIn("never took focus", str(raised.exception))

    def test_a_control_that_kept_the_text_passes(self):
        page_with(FILLED).fill(1, "admin@indoora.com")

    def test_a_field_that_reformats_what_it_is_given_is_not_a_failure(self):
        """A phone or date mask has done its job; failing it makes it untestable."""
        page = page_with({**FILLED, "value": "(555) 010-2030", "type": "tel"})
        page.fill(1, "5550102030")

    def test_a_control_with_nothing_to_read_back_is_not_judged(self):
        for state in (None, {"fillable": False, "value": "", "focused": False}):
            page_with(state).fill(1, "anything")

    def test_an_empty_fill_asserts_nothing(self):
        """Clearing a field is a legitimate thing for a journey to do."""
        page_with({**FILLED, "value": ""}).fill(1, "")

    def test_select_all_carries_the_key_code_that_makes_it_a_shortcut(self):
        page = page_with(FILLED)
        page.fill(1, "admin@indoora.com")
        keys = [params for method, params in page.cdp.sent
                if method == "Input.dispatchKeyEvent"]
        self.assertTrue(keys)
        for params in keys:
            self.assertEqual(params.get("windowsVirtualKeyCode"), 65)


class SnapshotValueTests(unittest.TestCase):
    """The value was always collected; it used to be dropped one line later."""

    def test_a_filled_control_shows_what_it_holds(self):
        page = page_with(tree=[ax("textbox", "Email", "admin@indoora.com")])
        self.assertIn("textbox: Email = 'admin@indoora.com'", page.snapshot())

    def test_an_empty_control_says_so_rather_than_looking_the_same(self):
        page = page_with(tree=[ax("textbox", "Email", "")])
        self.assertIn("textbox: Email = (empty)", page.snapshot())

    def test_two_fields_holding_different_things_are_two_rows(self):
        """Deduplication used to collapse them, because only the name was shown."""
        page = page_with(tree=[ax("textbox", "Email", "a@b.com"),
                               ax("textbox", "Email", "")])
        self.assertEqual(page.snapshot().count("textbox: Email"), 2)

    def test_something_that_is_not_a_value_keeps_its_plain_row(self):
        page = page_with(tree=[ax("button", "Sign in")])
        self.assertIn("button: Sign in", page.snapshot())
        self.assertNotIn("(empty)", page.snapshot())


class FormStateTests(unittest.TestCase):
    """What a failed journey now reports instead of a picture."""

    class Page:
        def __init__(self, rows):
            self.rows = rows

        def evaluate(self, expression, timeout=None):
            if isinstance(self.rows, Exception):
                raise self.rows
            return self.rows

    def test_it_names_each_control_and_what_it_held(self):
        said = form_state(self.Page([
            {"tag": "input", "type": "email", "label": "email", "value": "", "focused": False},
            {"tag": "input", "type": "password", "label": "password",
             "value": "admin123", "focused": True},
        ]))
        self.assertIn("input[email] email: (empty)", said)
        self.assertIn("input[password] password: 'admin123'", said)
        self.assertIn("has focus", said)

    def test_a_page_with_no_controls_says_nothing_at_all(self):
        self.assertEqual(form_state(self.Page([])), "")

    def test_a_page_too_broken_to_read_does_not_break_the_report(self):
        self.assertEqual(form_state(self.Page(RuntimeError("no execution context"))), "")


class NoPerStepPicturesTests(unittest.TestCase):
    def test_a_journey_no_longer_photographs_every_step(self):
        self.assertFalse(hasattr(__import__("builder_agent.journeys", fromlist=["x"]),
                                 "_frame"))

    def test_the_named_evidence_screenshot_step_survives(self):
        """A journey can still ask for a picture; it just is not given one per step."""
        import inspect

        from builder_agent import journeys
        self.assertIn("page.screenshot(", inspect.getsource(journeys.run_journey))


if __name__ == "__main__":
    unittest.main()
