"""Redrawing the pages a prototype change actually touched.

Until now a change of any size redrew every page of the specification, from the
specification, and did it after the transaction that caused it had already
returned. So the drawing cost seventeen model calls for a one-line edit, it was
a drawing of what the document said rather than of what the product does, and
the project adopted the previous version's copies because the new ones did not
exist yet.

What is checked here is the narrow version: the named pages and no others, the
prototype's own structure reaching the prompt, one page's failure costing that
page alone, and the drawing being finished rather than scheduled.
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from test._support import ROOT  # noqa: F401 - puts the agent packages on sys.path

from srs_agent.app.agents import wireframe_generator as wf

DOC = {
    "version": "1.3.0",
    "public_pages": [{"route": "/", "page_name": "Landing Page"},
                     {"route": "/rooms", "page_name": "Room Gallery"}],
    "protected_pages": [{"route": "/admin", "page_name": "Admin Dashboard"}],
}


class RedrawTests(unittest.TestCase):
    def setUp(self):
        self.saved = {}
        self.drawn = []

        def save(project_id, route, html, version=""):
            self.saved[route] = (html, version)

        self.storage = patch.object(wf, "handoff_context", return_value="APP DOCS")
        self.storage.start()
        self.addCleanup(self.storage.stop)
        self.save_patch = patch("srs_agent.app.services.storage.save_page_html", save)
        self.save_patch.start()
        self.addCleanup(self.save_patch.stop)

    def draw(self, pages, drafter=None):
        async def draft(page, doc, context="", structure=""):
            self.drawn.append({"route": page.get("route"), "context": context,
                               "structure": structure})
            return f"<html><body>{page.get('page_name')}</body></html>"

        with patch.object(wf, "draft_html_wireframe", drafter or draft):
            return asyncio.run(wf.redraw_pages("prj_a", DOC, pages))

    def test_only_the_pages_that_changed_are_drawn(self):
        drawn = self.draw([{"route": "/rooms", "outline": "main\n  h1 'Rooms'"}])
        self.assertEqual(drawn, ["/rooms"])
        self.assertEqual(sorted(self.saved), ["/rooms"])

    def test_the_prototype_structure_is_what_the_page_is_drawn_from(self):
        self.draw([{"route": "/", "outline": "header#navbar\n  a 'Home'"}])
        self.assertEqual(self.drawn[0]["structure"], "header#navbar\n  a 'Home'")
        self.assertEqual(self.drawn[0]["context"], "APP DOCS")

    def test_the_drawing_is_stamped_with_the_version_it_was_made_from(self):
        """Without the stamp the editor cannot say that a page has gone stale."""
        self.draw([{"route": "/", "outline": "main"}])
        self.assertEqual(self.saved["/"][1], "1.3.0")

    def test_a_page_the_specification_does_not_name_is_not_invented(self):
        self.assertEqual(self.draw([{"route": "/profile", "outline": "main"}]), [])
        self.assertEqual(self.saved, {})

    def test_a_page_with_no_structure_is_left_to_the_full_drawing(self):
        self.assertEqual(self.draw([{"route": "/", "outline": ""}]), [])

    def test_one_page_failing_does_not_cost_the_others(self):
        async def draft(page, doc, context="", structure=""):
            if page.get("route") == "/":
                raise RuntimeError("the model returned prose")
            return "<html>ok</html>"

        drawn = self.draw([{"route": "/", "outline": "main"},
                           {"route": "/rooms", "outline": "main"}], drafter=draft)
        self.assertEqual(drawn, ["/rooms"])

    def test_nothing_is_left_marked_as_drawing_afterwards(self):
        self.draw([{"route": "/", "outline": "main"}])
        self.assertFalse(wf.drawing("prj_a"))


if __name__ == "__main__":
    unittest.main()


class BlanketRedrawTests(unittest.TestCase):
    """When the whole set is worth redrawing, and when it is only worth its cost.

    A page is a model call, so the blanket pass is seventeen of them for a
    seventeen-page product. It used to run on every change that reached the
    document, including a QA report, which moves a verification status and not
    a single pixel.
    """

    def _pages(self, *drawn):
        return {"pages": [{"route": f"/p{n}", "has_html": has} for n, has in enumerate(drawn)]}

    def test_a_document_that_did_not_move_is_not_redrawn(self):
        from srs_agent.app.services import parent_sync
        with patch.object(parent_sync.storage, "read_wireframes",
                          return_value=self._pages(True, True)):
            self.assertFalse(parent_sync._undrawn("prj_a"))

    def test_a_page_that_was_never_drawn_still_asks_for_the_pass(self):
        from srs_agent.app.services import parent_sync
        with patch.object(parent_sync.storage, "read_wireframes",
                          return_value=self._pages(True, False)):
            self.assertTrue(parent_sync._undrawn("prj_a"))
