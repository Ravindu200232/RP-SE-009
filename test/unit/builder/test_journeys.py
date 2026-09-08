"""Browser journeys: what counts as a failure, and who owns it.

The diagnostics check is what makes a journey more than a screenshot — it
catches the page that renders correctly while throwing in the console. It is
also the check most able to make a whole stage useless: judge it too harshly
and every journey on every app fails forever, and no amount of repair helps
because nothing was ever broken.
"""
from __future__ import annotations

import unittest

from test import _support  # noqa: F401
from builder_agent.browser import CANCELLED_ERRORS, request_outcome
from builder_agent.errors import ToolError
from builder_agent.journeys import _assert, diagnostics_report


class FakePage:
    """A page with a chosen set of diagnostics and text."""

    def __init__(self, diagnostics=(), text="", url="http://localhost:3200/"):
        self.diagnostics = list(diagnostics)
        self._text = text
        self.url = url

    def text(self, limit=6000):
        return self._text


def note(kind, text="", url=""):
    return {"kind": kind, "text": text, "url": url}


class DiagnosticsTests(unittest.TestCase):
    def test_a_clean_page_passes(self):
        passed, detail = _assert(FakePage(), {"type": "noDiagnostics"})
        self.assertTrue(passed)
        self.assertIn("no critical", detail)

    def test_a_console_error_fails_the_journey(self):
        passed, detail = _assert(
            FakePage([note("console error", "Cannot read properties of undefined")]),
            {"type": "noDiagnostics"})
        self.assertFalse(passed)
        self.assertIn("Cannot read properties", detail)

    def test_a_server_error_fails_the_journey(self):
        passed, _ = _assert(FakePage([note("HTTP 500", "Internal Server Error")]),
                            {"type": "noDiagnostics"})
        self.assertFalse(passed)

    def test_a_genuinely_failed_request_fails_the_journey(self):
        passed, _ = _assert(FakePage([note("request failed", "net::ERR_CONNECTION_REFUSED")]),
                            {"type": "noDiagnostics"})
        self.assertFalse(passed)

    def test_a_cancelled_request_does_not_fail_the_journey(self):
        """The one that mattered.

        A framework that prefetches routes cancels those prefetches on every
        navigation. Counting them as defects failed every journey of a real
        build, and the repair loop could not converge because there was
        nothing to repair.
        """
        cancelled = [note("request cancelled", "net::ERR_ABORTED") for _ in range(15)]
        passed, detail = _assert(FakePage(cancelled), {"type": "noDiagnostics"})

        self.assertTrue(passed, detail)

    def test_cancellations_are_still_visible_when_a_failure_is_investigated(self):
        page = FakePage([note("request cancelled", "net::ERR_ABORTED", "/books")])
        self.assertIn("net::ERR_ABORTED", diagnostics_report(page))

    def test_a_cancellation_beside_a_real_failure_still_fails(self):
        passed, detail = _assert(
            FakePage([note("request cancelled", "net::ERR_ABORTED"),
                      note("page error", "TypeError: books.map is not a function")]),
            {"type": "noDiagnostics"})
        self.assertFalse(passed)
        self.assertIn("TypeError", detail)
        self.assertIn("1 critical", detail)


class RequestClassificationTests(unittest.TestCase):
    def classify(self, error, canceled=False):
        """The rule the CDP listener applies, over one `loadingFailed` payload."""
        return request_outcome({"errorText": error, "canceled": canceled, "url": "/x"})

    def test_cdp_calling_a_request_cancelled_is_believed(self):
        self.assertEqual(self.classify("net::ERR_FAILED", canceled=True), "request cancelled")

    def test_the_error_text_is_the_backstop(self):
        for error in CANCELLED_ERRORS:
            self.assertEqual(self.classify(error), "request cancelled", error)

    def test_a_connection_that_was_refused_is_a_failure(self):
        for error in ("net::ERR_CONNECTION_REFUSED", "net::ERR_NAME_NOT_RESOLVED",
                      "net::ERR_TIMED_OUT", "net::ERR_EMPTY_RESPONSE"):
            self.assertEqual(self.classify(error), "request failed", error)


class LocatorTests(unittest.TestCase):
    """Choosing one element out of several, and saying how when it cannot."""

    def pick(self, count, index=None):
        from builder_agent.browser import Page
        return Page._pick(list(range(100, 100 + count)), index, "role link")

    def test_one_match_needs_no_index(self):
        self.assertEqual(self.pick(1), 100)

    def test_an_index_chooses_from_a_repeated_control(self):
        """A list page repeats its controls once per row. That is correct UI.

        Without a way to say which one, no list page could ever be tested and
        the stage told the model to fix a product that was not broken.
        """
        self.assertEqual(self.pick(3, 0), 100)
        self.assertEqual(self.pick(3, 2), 102)
        self.assertEqual(self.pick(3, -1), 102)

    def test_ambiguity_says_how_to_resolve_it(self):
        with self.assertRaises(ToolError) as caught:
            self.pick(3)
        message = str(caught.exception)
        self.assertIn("E2E_SELECTOR_AMBIGUOUS", message)
        self.assertIn("index:0", message)
        # And that a repeated control is not something to "fix" in the product.
        self.assertIn("not a product defect", message)

    def test_an_index_past_the_end_is_the_journey_being_wrong(self):
        with self.assertRaises(ToolError) as caught:
            self.pick(2, 5)
        self.assertIn("out of range", str(caught.exception))
        self.assertIn("E2E_SELECTOR_MISMATCH", str(caught.exception))


class AssertionShapeTests(unittest.TestCase):
    def test_an_empty_expectation_is_refused_rather_than_always_passing(self):
        for kind in ("textIncludes", "urlIncludes"):
            with self.assertRaises(ToolError, msg=kind):
                _assert(FakePage(), {"type": kind, "expected": ""})

    def test_text_and_url_assertions_report_what_they_actually_saw(self):
        page = FakePage(text="Six books in stock", url="http://localhost:3200/books")

        passed, detail = _assert(page, {"type": "textIncludes", "expected": "Six books"})
        self.assertTrue(passed)

        passed, detail = _assert(page, {"type": "textIncludes", "expected": "Nine books"})
        self.assertFalse(passed)
        self.assertIn("Six books in stock", detail)

        passed, _ = _assert(page, {"type": "urlIncludes", "expected": "/books"})
        self.assertTrue(passed)

    def test_an_unknown_assertion_names_the_ones_that_exist(self):
        with self.assertRaises(ToolError) as caught:
            _assert(FakePage(), {"type": "looksNice"})
        self.assertIn("textIncludes", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
