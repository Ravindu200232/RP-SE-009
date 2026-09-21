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
from qa_agent import browser
from builder_agent.errors import ToolError
from qa_agent.journeys import form_state

FILLED = {"fillable": True, "value": "admin@indoora.com", "focused": True,
          "tag": "input", "type": "email", "label": "email"}


class FakeCdp:
    """Enough of the protocol for one control and one page."""

    def __init__(self, control=None, tree=(), url="http://localhost:5173/login",
                 inspection=None):
        self.control, self.tree, self.page_url = control, list(tree), url
        self.inspection = inspection
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
            asked = (params or {}).get("functionDeclaration", "")
            if "elementFromPoint" in asked:
                return {"result": {"value": self.inspection}}
            return {"result": {"value": self.control}}
        if method == "Accessibility.getFullAXTree":
            return {"nodes": self.tree}
        if method == "Runtime.evaluate":
            expression = (params or {}).get("expression", "")
            return {"result": {"value": self.page_url if "location.href" in expression else 1}}
        return {}


def page_with(control=None, tree=(), url="http://localhost:5173/login", inspection=None):
    return browser.Page(FakeCdp(control, tree, url, inspection), "target-1", "session-1")


SEEN = {"pointHits": "input#email", "pointPath": "input#email < form", "hitIsTarget": True,
        "hitInsideTarget": True, "activeElement": "input#email", "stillInDocument": True,
        "rect": "x=462 y=336 w=324 h=23", "pointerEvents": "auto", "visibility": "visible",
        "opacity": "1", "disabled": False, "readOnly": False, "pageVisibility": "visible",
        "pageHasFocus": True,
        "viewport": {"w": 1264, "h": 649, "dpr": 1,
                     "vv": {"w": 1249, "h": 649, "scale": 1, "ox": 0, "oy": 0}}}


def failing(**overrides):
    """A page whose fill fails, with the page reporting `overrides`."""
    return page_with({**FILLED, "value": "", "focused": False},
                     inspection={**SEEN, **overrides})


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

    def test_text_that_arrived_passes_even_if_focus_has_moved_on(self):
        """Some pages blur a field as soon as it is filled. The text landed."""
        page_with({**FILLED, "focused": False}).fill(1, "admin@indoora.com")

    def test_a_stale_value_left_by_a_click_that_missed_is_a_failure(self):
        """`fill` selects all and replaces, so the old text means it never ran."""
        page = page_with({**FILLED, "value": "someone.else@example.com", "focused": False},
                         inspection={**SEEN, "hitIsTarget": False, "hitInsideTarget": False,
                                     "pointHits": "div.modal-overlay"})
        with self.assertRaises(ToolError) as raised:
            page.fill(1, "admin@indoora.com")
        said = str(raised.exception)
        self.assertIn("someone.else@example.com", said)
        self.assertIn("div.modal-overlay", said)

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

    def test_fill_focuses_the_resolved_control_before_sending_text(self):
        """Input.insertText must not depend on a mouse click having focused it."""
        page = page_with(FILLED)
        page.fill(1, "admin@indoora.com")
        methods = [method for method, _ in page.cdp.sent]
        self.assertIn("DOM.focus", methods)
        self.assertLess(methods.index("DOM.focus"), methods.index("Input.insertText"))

    def test_fill_exposes_the_action_point_but_never_the_typed_text(self):
        page = page_with(FILLED)
        page.fill(1, "admin@indoora.com")
        self.assertEqual(page.cursor["action"], "type")
        self.assertEqual((page.cursor["x"], page.cursor["y"]), (5.0, 5.0))
        self.assertNotIn("admin@indoora.com", page.cursor.values())


class WhyItFailedTests(unittest.TestCase):
    """The message says what the page reported, and nothing it did not.

    The first version of this error guessed - it told every reader that
    something was covering the control, because that is the usual reason. A
    guess in an error message is worse than silence: the next reader repairs
    the thing it names.
    """

    def message(self, **overrides):
        with self.assertRaises(ToolError) as raised:
            failing(**overrides).fill(1, "guest@indoora.com")
        return str(raised.exception)

    def test_something_on_top_is_named(self):
        said = self.message(pointHits="div#cookie-banner", hitIsTarget=False,
                            hitInsideTarget=False,
                            pointPath="div#cookie-banner < div.row < body")
        self.assertIn("div#cookie-banner", said)
        self.assertIn("not on the control", said)

    def test_a_disabled_control_is_not_blamed_on_an_overlay(self):
        said = self.message(disabled=True)
        self.assertIn("disabled", said)
        self.assertNotIn("landed on", said)

    def test_a_read_only_control_says_so(self):
        self.assertIn("read-only", self.message(readOnly=True))

    def test_a_node_the_page_replaced_is_reported_as_that(self):
        said = self.message(stillInDocument=False)
        self.assertIn("taken out of the document", said)
        self.assertIn("re-rendered", said)

    def test_a_detached_node_is_not_described_by_its_computed_style(self):
        """A node out of the document has none, so there is nothing to report."""
        said = self.message(stillInDocument=False, visibility="", opacity="")
        self.assertNotIn("opacity", said)

    def test_pointer_events_none_is_called_out(self):
        self.assertIn("pointer-events is none", self.message(pointerEvents="none"))

    def test_a_click_that_did_reach_it_says_where_focus_went_instead(self):
        said = self.message(hitIsTarget=True, activeElement="body")
        self.assertIn("did reach the control", said)
        self.assertIn("body", said)
        self.assertNotIn("something is covering", said)

    def test_a_scaled_visual_viewport_is_reported_as_a_coordinate_mismatch(self):
        said = self.message(viewport={"w": 1264, "h": 649, "dpr": 1,
                                      "vv": {"w": 900, "h": 675, "scale": 0.72,
                                             "ox": 0, "oy": 0}})
        self.assertIn("0.72", said)
        self.assertIn("do not match", said)

    def test_a_page_without_focus_says_so(self):
        self.assertIn("did not have focus", self.message(pageHasFocus=False))

    def test_a_page_that_cannot_be_read_admits_it_rather_than_guessing(self):
        page = page_with({**FILLED, "value": "", "focused": False}, inspection=None)
        with self.assertRaises(ToolError) as raised:
            page.fill(1, "guest@indoora.com")
        self.assertIn("is not known", str(raised.exception))

    def test_the_click_point_is_the_one_the_click_used(self):
        said = self.message(hitIsTarget=False, hitInsideTarget=False, pointHits="div")
        self.assertIn("(5, 5)", said)      # the fake box model's centre


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
        self.assertFalse(hasattr(__import__("qa_agent.journeys", fromlist=["x"]),
                                 "_frame"))

    def test_the_named_evidence_screenshot_step_survives(self):
        """A journey can still ask for a picture; it just is not given one per step."""
        import inspect

        from qa_agent import journeys
        self.assertIn("page.screenshot(", inspect.getsource(journeys.run_journey))


if __name__ == "__main__":
    unittest.main()
