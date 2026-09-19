"""The gap between an approved specification and its drawings.

Approving a specification schedules one model call per page and waits for
none of them, so for the first half minute the page list is complete and every
drawing is missing. That state is indistinguishable, from the studio, from a
project whose pages failed - and it was shown as "not drawn yet" on every card,
with no indication that anything was still happening.

So the read says whether a drawing is running. What is tested here is that the
flag is honest in both directions: a finished task is not a running one, and
one project's drawing is not another's.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "srs-agent"))

from srs_agent.app.agents import wireframe_generator as wf  # noqa: E402


class Task:
    """An asyncio task, as far as `drawing` is concerned."""

    def __init__(self, finished: bool = False):
        self._finished = finished

    def done(self) -> bool:
        return self._finished


class DrawingFlagTests(unittest.TestCase):
    def setUp(self):
        self.saved = dict(wf._IN_FLIGHT)
        wf._IN_FLIGHT.clear()
        self.addCleanup(lambda: (wf._IN_FLIGHT.clear(), wf._IN_FLIGHT.update(self.saved)))

    def test_nothing_running_is_not_drawing(self):
        self.assertFalse(wf.drawing("prj_a"))

    def test_a_running_task_for_this_project_is_drawing(self):
        wf._IN_FLIGHT[("prj_a", "1.0.0")] = Task()
        self.assertTrue(wf.drawing("prj_a"))

    def test_another_project_is_not_this_one(self):
        """Two specifications drawn at once must not wait on each other."""
        wf._IN_FLIGHT[("prj_b", "1.0.0")] = Task()
        self.assertFalse(wf.drawing("prj_a"))
        self.assertTrue(wf.drawing("prj_b"))

    def test_a_finished_task_is_not_still_drawing(self):
        """The task is kept as a strong reference after it ends; the flag is not."""
        wf._IN_FLIGHT[("prj_a", "1.0.0")] = Task(finished=True)
        self.assertFalse(wf.drawing("prj_a"))

    def test_a_later_version_drawing_still_counts(self):
        wf._IN_FLIGHT[("prj_a", "1.0.0")] = Task(finished=True)
        wf._IN_FLIGHT[("prj_a", "1.1.0")] = Task()
        self.assertTrue(wf.drawing("prj_a"))

    def test_an_object_that_is_not_a_task_does_not_break_the_read(self):
        """A read of this must never be the thing that fails a page load."""
        wf._IN_FLIGHT[("prj_a", "1.0.0")] = object()
        self.assertTrue(wf.drawing("prj_a"))


class RouteTests(unittest.TestCase):
    def test_the_read_carries_the_flag(self):
        import inspect
        from srs_agent.app.routers import srs
        source = inspect.getsource(srs.wireframes)
        self.assertIn('"drawing"', source)
        self.assertIn("drawing_now(project_id)", source)


if __name__ == "__main__":
    unittest.main()
