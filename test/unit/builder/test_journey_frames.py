"""A picture after every step, and what it must not cost.

The point of a frame is that nobody waits for it. A capture costs the browser
about 60 ms however it is asked for - scaling it down does not help, because
the cost is the round trip and the compositor grab rather than the encode - so
twelve of them is 29% of a twelve-step journey if the journey blocks on each.
Measured after the change: +1 ms over twelve steps, 72 of 72 frames written.

What is tested here is the shape that makes that true, and the fact that a
frame is deliberately not evidence: `capture_visual` resets a record to
"captured / not visually reviewed" on every write and ages it against the
revision, so a run's worth of frames as evidence would arrive as dozens of
visual records all marked outdated.
"""
from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path

from test import _support  # noqa: F401
from builder_agent import journeys


class FrameTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    class Sandbox:
        def __init__(self, root):
            self.root = root

        def state_dir(self, name):
            target = self.root / ".agent" / name
            target.mkdir(parents=True, exist_ok=True)
            return target

    class Page:
        def __init__(self):
            self.asked = []

        def frame(self, path, quality=55, scale=0.5):
            self.asked.append({"path": Path(path), "quality": quality, "scale": scale})

    def test_a_frame_is_named_for_the_step_it_followed(self):
        page, sandbox = self.Page(), self.Sandbox(self.root)
        journeys._frame(page, sandbox, "Checkout journey", 7, "click")
        self.assertEqual(len(page.asked), 1)
        self.assertEqual(page.asked[0]["path"].name, "checkout-journey-07-click.jpg")

    def test_the_index_is_padded_so_ten_steps_sort_after_nine(self):
        page, sandbox = self.Page(), self.Sandbox(self.root)
        for index in (2, 10):
            journeys._frame(page, sandbox, "s", index, "click")
        names = sorted(shot["path"].name for shot in page.asked)
        self.assertEqual(names, ["s-02-click.jpg", "s-10-click.jpg"])

    def test_a_browser_that_cannot_capture_does_not_fail_the_journey(self):
        class Broken:
            def frame(self, *a, **k):
                raise RuntimeError("the tab went away")
        journeys._frame(Broken(), self.Sandbox(self.root), "s", 1, "click")

    def test_the_journey_never_waits_for_one(self):
        """`page.frame` is the non-blocking call; `page.screenshot` is not."""
        source = inspect.getsource(journeys._frame)
        self.assertIn("page.frame(", source)
        self.assertNotIn("page.screenshot(", source)

    def test_a_frame_is_never_recorded_as_visual_evidence(self):
        source = inspect.getsource(journeys._frame)
        self.assertNotIn("capture_visual", source)

    def test_every_dispatched_step_is_framed_including_the_one_that_failed(self):
        """The picture of the step that broke is the most useful in the run."""
        source = inspect.getsource(journeys.run_journey)
        self.assertEqual(source.count("_frame(page, sandbox, suite, index, action)"), 3)


class BrowserContractTests(unittest.TestCase):
    """What `Page.frame` and the call under it promise."""

    def test_the_capture_is_asked_for_without_waiting_on_the_reply(self):
        from builder_agent import browser
        source = inspect.getsource(browser.Page.frame)
        self.assertIn("self.cdp.ask(", source)
        self.assertNotIn("self.cdp.send(", source)

    def test_an_unwaited_call_still_keeps_its_result(self):
        """`post` forgets the reply; a frame's reply is the picture."""
        from builder_agent import browser
        self.assertIn("then", inspect.signature(browser.Cdp.ask).parameters)

    def test_an_evidence_shot_still_sizes_and_settles(self):
        """A frame skips both; the named-width evidence shot must not."""
        from builder_agent import browser
        signature = inspect.signature(browser.Page.screenshot).parameters
        self.assertTrue(signature["settle"].default)
        self.assertTrue(signature["resize"].default)


if __name__ == "__main__":
    unittest.main()
