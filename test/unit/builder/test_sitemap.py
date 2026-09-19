"""The screens, and how they reach each other, kept between the passes."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from test import _support  # noqa: F401
from builder_agent import sitemap


class FromThePlanTests(unittest.TestCase):
    def test_a_route_becomes_the_file_the_drawing_will_write(self):
        entries = sitemap.from_screens([
            {"route": "/", "label": "Home", "what": "front"},
            {"route": "/admin/orders", "label": "Orders", "what": "staff"},
            {"route": "/rooms/[id]", "label": "Room", "what": "one room"}])
        self.assertEqual([e["file"] for e in entries],
                         ["index.html", "admin-orders.html", "rooms-id.html"])

    def test_the_same_screen_twice_is_one_entry(self):
        entries = sitemap.from_screens([{"route": "/rooms"}, {"route": "/rooms/"}])
        self.assertEqual(len(entries), 1)

    def test_nothing_planned_is_an_empty_map_not_a_crash(self):
        self.assertEqual(sitemap.from_screens([]), [])
        self.assertEqual(sitemap.render([]), "")


class FromTheDrawingTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "index.html").write_text(
            '<title>Home | Royal</title><a href="rooms.html">Rooms</a>'
            '<a href="rooms.html">again</a><a href="https://x.com/a.html">out</a>',
            encoding="utf-8")
        (self.root / "rooms.html").write_text(
            '<title>Rooms | Royal</title><a href="index.html">Home</a>', encoding="utf-8")

    def test_it_records_where_each_page_can_take_somebody(self):
        entries = {e["file"]: e for e in sitemap.from_drawing(self.root)}
        # Deduplicated, and a page does not link to itself.
        self.assertEqual(entries["index.html"]["links"], ["rooms.html"])
        self.assertEqual(entries["rooms.html"]["links"], ["index.html"])

    def test_a_title_becomes_the_label_when_the_plan_gave_none(self):
        entries = {e["file"]: e for e in sitemap.from_drawing(self.root)}
        self.assertEqual(entries["index.html"]["label"], "Home")

    def test_a_planned_screen_that_is_not_drawn_yet_survives_and_is_marked(self):
        planned = sitemap.from_screens([{"route": "/", "label": "Home"},
                                        {"route": "/admin", "label": "Admin"}])
        entries = {e["file"]: e for e in sitemap.from_drawing(self.root, planned)}
        self.assertIn("admin.html", entries)
        self.assertFalse(entries["admin.html"]["drawn"])
        self.assertTrue(entries["index.html"]["drawn"])
        self.assertIn("[NOT DRAWN YET]", sitemap.render(list(entries.values()), drawn=True))

    def test_a_page_the_drawing_added_joins_the_map(self):
        (self.root / "offers.html").write_text("<title>Offers</title>", encoding="utf-8")
        self.assertIn("offers.html", [e["file"] for e in sitemap.from_drawing(self.root)])

    def test_a_page_nothing_links_to_is_named(self):
        (self.root / "offers.html").write_text("<title>Offers</title>", encoding="utf-8")
        entries = sitemap.from_drawing(self.root)
        self.assertEqual(sitemap.unreachable(entries), ["offers.html"])
        self.assertIn("Nothing links to: offers.html", sitemap.render(entries, drawn=True))

    def test_the_way_in_is_never_called_unreachable(self):
        self.assertNotIn("index.html", sitemap.unreachable(sitemap.from_drawing(self.root)))


class PersistenceTests(unittest.TestCase):
    def test_it_survives_a_round_trip_through_the_project(self):
        root = Path(tempfile.mkdtemp())
        entries = sitemap.from_screens([{"route": "/", "label": "Home"}])
        sitemap.save(root, entries)
        self.assertEqual(sitemap.load(root), entries)

    def test_no_file_is_an_empty_map(self):
        self.assertEqual(sitemap.load(Path(tempfile.mkdtemp())), [])


class DeadEndsTests(unittest.TestCase):
    """A link that lands on nothing is the other half of an unfinished app.

    Orphans - pages nobody can reach - were reported. Dead ends were not, and
    they are the ones a person actually hits: a bakery linked four pages at
    `rooms.html` and never wrote it.
    """

    ENTRIES = [
        {"file": "index.html", "drawn": True, "links": ["models.html", "gone.html"]},
        {"file": "models.html", "drawn": True, "links": ["index.html"]},
        {"file": "admin.html", "drawn": True, "links": []},
    ]

    def test_a_link_with_no_page_behind_it_is_named(self):
        self.assertEqual(sitemap.dangling(self.ENTRIES), ["gone.html"])

    def test_a_page_that_exists_is_not(self):
        self.assertNotIn("models.html", sitemap.dangling(self.ENTRIES))

    def test_both_faults_are_reported_and_they_are_different_faults(self):
        text = sitemap.render(self.ENTRIES, drawn=True)
        self.assertIn("Nothing links to: admin.html", text)
        self.assertIn("Linked but missing: gone.html", text)

    def test_a_whole_map_says_so_rather_than_saying_nothing(self):
        whole = [{"file": "index.html", "drawn": True, "links": ["a.html"]},
                 {"file": "a.html", "drawn": True, "links": ["index.html"]}]
        self.assertIn("every link lands", sitemap.render(whole, drawn=True))
