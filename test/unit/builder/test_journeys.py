"""Browser journeys: what counts as a failure, and who owns it.

The diagnostics check is what makes a journey more than a screenshot — it
catches the page that renders correctly while throwing in the console. It is
also the check most able to make a whole stage useless: judge it too harshly
and every journey on every app fails forever, and no amount of repair helps
because nothing was ever broken.
"""
from __future__ import annotations

import types
import unittest

from test import _support  # noqa: F401
from builder_agent import browser
from builder_agent.browser import CANCELLED_ERRORS, request_outcome
from builder_agent.errors import ToolError
from builder_agent.evidence import Evidence
from builder_agent.journeys import _assert, diagnostics_report, run_journey


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


class JourneyRepairTests(unittest.TestCase):
    def test_a_corrected_locator_retries_the_same_suite_without_a_product_edit(self):
        page = FakePage(text="Your books")
        clicks = []

        def locate(role, name, selector, index):
            if selector != '[data-filter="read"]':
                raise ToolError("E2E_SELECTOR_MISMATCH: repair the journey locator")
            return "read-tab"

        page.locate = locate
        page.click = clicks.append
        page.wait_ready = lambda timeout: None
        page.reset_diagnostics = lambda: None
        driver = types.SimpleNamespace(page=lambda tab: page, attempts={},
                                       fresh_session=lambda: None)
        evidence = Evidence()
        revision = evidence.revision
        for name in ("Read", "Read books"):
            with self.assertRaisesRegex(ToolError, "E2E_SELECTOR_MISMATCH"):
                run_journey(driver, None, evidence, suite="filter", covers=[],
                            steps=[{"action": "click", "role": "tab", "name": name}])

        result = run_journey(driver, None, evidence, suite="filter", covers=[],
                             steps=[{"action": "click", "selector": '[data-filter="read"]'}])
        self.assertTrue(result["ok"])
        self.assertEqual(clicks, ["read-tab"])
        self.assertEqual(evidence.revision, revision)
        self.assertEqual(len(evidence.suites), 1)
        self.assertEqual(evidence.suites[0]["status"], "passed")


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


class ScreencastTests(unittest.TestCase):
    """What the studio shows of the agent's browser depends on one message."""

    def cast(self):
        """A page whose transport records what it was asked to do."""
        cdp = types.SimpleNamespace(
            handlers={}, sent=[], posted=[],
            on=lambda method, handler: cdp.handlers.setdefault(method, []).append(handler),
            send=lambda *a, **k: cdp.sent.append(a) or {},
            post=lambda *a, **k: cdp.posted.append(a))
        page = browser.Page.__new__(browser.Page)
        page.cdp, page.session = cdp, "s1"
        frames = []
        page.start_screencast(frames.append)
        return cdp, page, frames

    def test_a_frame_is_acknowledged_without_waiting_for_the_reply(self):
        """The handler runs on the socket's thread; `send` there deadlocks it.

        Chrome sends the next frame only once the last one is acknowledged, so
        an acknowledgement that blocks stops the stream after frame one — which
        is exactly what a still, silent preview looked like.
        """
        cdp, _, frames = self.cast()
        opening = list(cdp.sent)                # starting the cast is the caller's
        cdp.handlers["Page.screencastFrame"][0](
            {"data": "AAAA", "sessionId": 7}, "s1")

        self.assertEqual([call[0] for call in cdp.posted], ["Page.screencastFrameAck"])
        self.assertEqual(cdp.posted[0][1], {"sessionId": 7})
        self.assertEqual(cdp.sent, opening)     # the frame itself waited on nothing
        self.assertEqual(frames, ["data:image/jpeg;base64,AAAA"])

    def test_a_frame_for_another_tab_is_not_this_tab_s_frame(self):
        cdp, _, frames = self.cast()
        cdp.handlers["Page.screencastFrame"][0]({"data": "AAAA"}, "other")
        self.assertEqual(frames, [])
        self.assertEqual(cdp.posted, [])

    def test_one_tab_streams_once_however_often_it_is_asked(self):
        """A journey on an already-watched tab must not open a second cast."""
        cdp, page, _ = self.cast()
        page.start_screencast(lambda frame: None)
        self.assertEqual(len(cdp.handlers["Page.screencastFrame"]), 1)
        self.assertEqual([call[0] for call in cdp.sent], ["Page.startScreencast"])


class BrowserWatchTests(unittest.TestCase):
    def test_every_tab_the_agent_opens_is_streamed_to_the_studio(self):
        """Not only journeys: most browser work is opening a page and looking."""
        events = Recorder()
        engine = browser.Browser.__new__(browser.Browser)
        engine.events = events
        page = types.SimpleNamespace(
            url_cached="http://localhost:3200/plants", started=[],
            start_screencast=lambda on_frame: page.started.append(on_frame))

        engine._watch(page)
        page.started[0]("data:image/jpeg;base64,AAAA")

        self.assertEqual(events.seen, [("browser", {
            "state": "frame", "frame": "data:image/jpeg;base64,AAAA",
            "url": "http://localhost:3200/plants"})])

    def test_closing_the_browser_says_so_rather_than_going_quiet(self):
        """A last frame left on screen is a preview nobody can use."""
        events = Recorder()
        engine = browser.Browser.__new__(browser.Browser)
        engine.events, engine.cdp, engine.process = events, None, None
        engine.pages, engine.active, engine.profile = {}, None, None

        engine.close()

        self.assertEqual(events.seen,
                         [("browser", {"state": "closed", "frame": "", "url": ""})])

    def test_a_run_with_nowhere_to_send_frames_does_not_stream(self):
        engine = browser.Browser.__new__(browser.Browser)
        engine.events = None
        page = types.SimpleNamespace(started=[],
                                     start_screencast=lambda f: page.started.append(f))
        engine._watch(page)
        self.assertEqual(page.started, [])


class Recorder:
    def __init__(self):
        self.seen = []

    def emit(self, event, /, **payload):
        self.seen.append((event, payload))



if __name__ == "__main__":
    unittest.main()
