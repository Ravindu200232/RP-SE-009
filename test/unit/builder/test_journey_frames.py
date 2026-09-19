"""The capture that is left, and what it must not cost.

A journey used to photograph the page after every step. The pictures were
cheap by design - asked for without waiting, half size, no device-metrics
override - but they were the wrong medium for the reader. What repairs a
failed journey is a model reading text, and a strip of JPEGs never said the
thing that mattered: that the form behind the failing URL was empty. That is
read out of the DOM now, at the moment of failure, by `journeys.form_state`.

What `Page.frame` still serves is the QA UI sweep, which walks every page of
the application and wants one picture of each. So the contract below is still
worth holding: the capture is asked for without blocking, and it is not the
named-width evidence shot, which must still size and settle.
"""
from __future__ import annotations

import inspect
import unittest

from test import _support  # noqa: F401
from builder_agent import browser, journeys


class BrowserContractTests(unittest.TestCase):
    """What `Page.frame` and the call under it promise."""

    def test_the_capture_is_asked_for_without_waiting_on_the_reply(self):
        source = inspect.getsource(browser.Page.frame)
        self.assertIn("self.cdp.ask(", source)
        self.assertNotIn("self.cdp.send(", source)

    def test_an_unwaited_call_still_keeps_its_result(self):
        """`post` forgets the reply; a frame's reply is the picture."""
        self.assertIn("then", inspect.signature(browser.Cdp.ask).parameters)

    def test_an_evidence_shot_still_sizes_and_settles(self):
        """A frame skips both; the named-width evidence shot must not."""
        signature = inspect.signature(browser.Page.screenshot).parameters
        self.assertTrue(signature["settle"].default)
        self.assertTrue(signature["resize"].default)

    def test_the_sweep_that_needs_it_still_has_it(self):
        """`Page.frame` exists for the UI sweep, not for journey steps."""
        self.assertTrue(callable(browser.Page.frame))


class JourneyEvidenceTests(unittest.TestCase):
    """A journey reports in text, and pays for nothing per step."""

    def test_a_journey_photographs_nothing_of_its_own_accord(self):
        source = inspect.getsource(journeys.run_journey)
        self.assertNotIn("page.frame(", source)

    def test_a_failure_reads_the_controls_instead(self):
        source = inspect.getsource(journeys.run_journey)
        self.assertIn("form_state(page)", source)

    def test_what_it_reads_reaches_both_the_record_and_the_model(self):
        """Durable evidence and the error the agent sees carry the same reading."""
        source = inspect.getsource(journeys.run_journey)
        self.assertEqual(source.count("{seen}"), 2)


if __name__ == "__main__":
    unittest.main()
