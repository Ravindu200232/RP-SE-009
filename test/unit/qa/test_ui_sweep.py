"""Every page read, not only the ones a journey opened.

The usability check ran in exactly one place - the `navigate` branch of a
journey step - so a page reached by clicking was never read, and a page no
journey visits was never read at all. On the thirteen-page specification this
was measured against, that was most of the application.

What is tested is the reading, not the browser: a sweep asks no model, asserts
nothing and fails nothing, so the only things that can be wrong are which
routes it decides to open and whether one bad page takes the rest down.
"""
from __future__ import annotations

import json
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from test import _support  # noqa: F401
from qa_agent import ui_sweep


def spec(root: Path, public=(), protected=()):
    directory = root / ".agentforge" / "srs"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "srs_latest.json").write_text(json.dumps({"srs_document": {
        "public_pages": list(public), "protected_pages": list(protected)}}), encoding="utf-8")
    return root


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def routes(self, **kwargs):
        return [row["route"] for row in ui_sweep.routes_for(spec(self.root, **kwargs))]

    def test_every_page_the_specification_names(self):
        self.assertEqual(
            self.routes(public=[{"page_name": "Home", "route": "/"},
                                {"page_name": "Rooms", "route": "/rooms"}],
                        protected=[{"page_name": "Admin", "route": "/admin"}]),
            ["/", "/rooms", "/admin"])

    def test_a_route_that_needs_a_record_is_skipped_rather_than_guessed(self):
        """`/rooms/[id]` with an invented id is a 404 dressed up as a page.

        And "no h1 heading" about a 404 is worse than no reading at all.
        """
        self.assertEqual(
            self.routes(public=[{"page_name": "Room", "route": "/rooms/[id]"},
                                {"page_name": "Post", "route": "/blog/:slug"},
                                {"page_name": "Item", "route": "/shop/{sku}"},
                                {"page_name": "Home", "route": "/"}]),
            ["/"])

    def test_a_page_listed_twice_is_read_once(self):
        self.assertEqual(
            self.routes(public=[{"page_name": "Home", "route": "/"},
                                {"page_name": "Home again", "route": "/"}]),
            ["/"])

    def test_a_project_with_no_specification_asks_for_no_pages(self):
        self.assertEqual(ui_sweep.routes_for(Path(tempfile.mkdtemp())), [])

    def test_the_list_is_bounded(self):
        many = [{"page_name": f"P{i}", "route": f"/p{i}"} for i in range(80)]
        self.assertEqual(len(self.routes(public=many)), ui_sweep.MAX_PAGES)

    def test_a_protected_page_is_marked_as_one(self):
        rows = ui_sweep.routes_for(spec(
            self.root, public=[{"page_name": "Home", "route": "/"}],
            protected=[{"page_name": "Admin", "route": "/admin", "allowed_roles": ["admin"]}]))
        self.assertEqual({row["route"]: row["login_required"] for row in rows},
                         {"/": False, "/admin": True})


class SweepTests(unittest.TestCase):
    class Page:
        def __init__(self, breaks=()):
            self.breaks, self.opened = set(breaks), []

        def navigate(self, url, timeout=20):
            self.opened.append(url)
            if any(bad in url for bad in self.breaks):
                raise RuntimeError("navigation timed out")

        def frame(self, path, quality=55, scale=0.5):
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_bytes(b"jpeg")

    class Browser:
        def __init__(self, page):
            self._page = page

        def page(self, tab_id=None):
            return self._page

    PAGES = [{"route": "/", "page": "Home"}, {"route": "/admin", "page": "Admin"}]

    def sweep(self, page, **kwargs):
        return ui_sweep.sweep(self.Browser(page), "http://127.0.0.1:3000/",
                              self.PAGES, **kwargs)

    def test_each_page_is_opened_once_against_the_running_app(self):
        page = self.Page()
        with unittest.mock.patch.object(ui_sweep, "capture_ui_quality", return_value={}), \
             unittest.mock.patch.object(ui_sweep, "ui_quality_note", return_value="clean"):
            rows = self.sweep(page)
        self.assertEqual(page.opened,
                         ["http://127.0.0.1:3000/", "http://127.0.0.1:3000/admin"])
        self.assertEqual([row["note"] for row in rows], ["clean", "clean"])

    def test_one_page_that_will_not_open_does_not_take_the_others_down(self):
        page = self.Page(breaks=["/admin"])
        with unittest.mock.patch.object(ui_sweep, "capture_ui_quality", return_value={}), \
             unittest.mock.patch.object(ui_sweep, "ui_quality_note", return_value="clean"):
            rows = self.sweep(page)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["note"], "clean")
        self.assertIn("timed out", rows[1]["error"])

    def test_a_picture_is_kept_for_each_page(self):
        page, shots = self.Page(), Path(tempfile.mkdtemp())
        with unittest.mock.patch.object(ui_sweep, "capture_ui_quality", return_value={}), \
             unittest.mock.patch.object(ui_sweep, "ui_quality_note", return_value="clean"):
            rows = self.sweep(page, shots_dir=shots)
        self.assertEqual(sorted(p.name for p in shots.glob("*.jpg")),
                         ["page-admin.jpg", "page.jpg"])
        self.assertEqual([row["shot"] for row in rows], ["page.jpg", "page-admin.jpg"])

    def test_no_runtime_means_no_reading_rather_than_an_error(self):
        self.assertEqual(ui_sweep.sweep(None, "", self.PAGES), [])
        self.assertEqual(ui_sweep.sweep(None, "http://x", []), [])

    def test_no_browser_says_so_instead_of_failing(self):
        class Broken:
            def page(self, tab_id=None):
                raise RuntimeError("chrome is not installed")
        rows = ui_sweep.sweep(Broken(), "http://x", self.PAGES)
        self.assertEqual(len(rows), 1)
        self.assertIn("chrome is not installed", rows[0]["error"])

    def test_the_summary_names_the_pages_worth_looking_at(self):
        self.assertEqual(ui_sweep.summarise([]), "")
        self.assertIn("all clean", ui_sweep.summarise([{"route": "/", "note": "clean"}]))
        said = ui_sweep.summarise([{"route": "/", "note": "clean"},
                                   {"route": "/admin", "note": "no h1 heading"}])
        self.assertIn("1 with findings", said)
        self.assertIn("/admin", said)


if __name__ == "__main__":
    unittest.main()
