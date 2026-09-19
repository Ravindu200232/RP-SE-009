"""Pairing a drawn page with the route the specification gives it.

The two halves of a project have always named their pages differently, and
nothing wrote the correspondence down. What is checked here is the awkward
half of that: not `rooms.html` meeting `/rooms`, which any rule would get, but
`admin-booking-detail.html` meeting `/admin/bookings/:id` while
`admin-bookings.html` keeps `/admin/bookings`, and a page the specification
never named staying unpaired instead of being forced onto the nearest route.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from test._support import ROOT  # noqa: F401 - puts the repository on sys.path

from server_modules.services import prototype_routes

PAGES = [
    {"route": "/", "page_name": "Landing Page"},
    {"route": "/rooms", "page_name": "Room Gallery"},
    {"route": "/rooms/:id", "page_name": "Room Detail"},
    {"route": "/admin", "page_name": "Admin Dashboard"},
    {"route": "/admin/bookings", "page_name": "Bookings List"},
    {"route": "/admin/bookings/:id", "page_name": "Booking Detail"},
    {"route": "/admin/rooms", "page_name": "Rooms List"},
    {"route": "/admin/rooms/:id", "page_name": "Room Edit"},
]

DRAWN = {
    "index.html": "Hotel Indoora - Boutique stays",
    "rooms.html": "Rooms - Hotel Indoora",
    "room-detail.html": "Room detail - Hotel Indoora",
    "admin.html": "Admin dashboard - Hotel Indoora",
    "admin-bookings.html": "Bookings - Hotel Indoora",
    "admin-booking-detail.html": "Booking detail - Hotel Indoora",
    "admin-rooms.html": "Rooms - Hotel Indoora",
    "admin-room-edit.html": "Edit room - Hotel Indoora",
    "booking-confirmation.html": "Booking confirmed - Hotel Indoora",
}


class PairingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name) / "app"
        self.prototype = self.project / ".agentforge" / "prototype"
        self.prototype.mkdir(parents=True)
        wireframes = self.project / ".agentforge" / "wireframes"
        wireframes.mkdir(parents=True)
        (wireframes / "wireframes.json").write_text(
            json.dumps({"version": "1.2.0", "pages": PAGES}), encoding="utf-8")
        for name, title in DRAWN.items():
            (self.prototype / name).write_text(
                f"<html><head><title>{title}</title></head><body><h1>{title}</h1></body></html>",
                encoding="utf-8")

    def pair(self, *names):
        return prototype_routes.route_for_files(
            self.project, [f".agentforge/prototype/{name}" for name in (names or DRAWN)])

    def test_every_drawn_page_finds_the_route_it_draws(self):
        self.assertEqual(self.pair(), {
            "index.html": "/",
            "rooms.html": "/rooms",
            "room-detail.html": "/rooms/:id",
            "admin.html": "/admin",
            "admin-bookings.html": "/admin/bookings",
            "admin-booking-detail.html": "/admin/bookings/:id",
            "admin-rooms.html": "/admin/rooms",
            "admin-room-edit.html": "/admin/rooms/:id",
        })

    def test_a_page_the_specification_never_named_stays_unpaired(self):
        """Inventing a route for it would put a screen into the specification."""
        self.assertNotIn("booking-confirmation.html", self.pair())

    def test_a_list_does_not_lose_its_route_to_a_detail_page(self):
        """Scored together, `admin-rooms.html` claims `/admin/rooms` on its slug first."""
        paired = self.pair("admin-room-edit.html", "admin-rooms.html")
        self.assertEqual(paired["admin-rooms.html"], "/admin/rooms")
        self.assertEqual(paired["admin-room-edit.html"], "/admin/rooms/:id")

    def test_a_written_sitemap_is_believed_over_the_scoring(self):
        (self.project / ".agentforge" / "sitemap.json").write_text(
            json.dumps([{"file": "room-detail.html", "route": "/rooms"}]), encoding="utf-8")
        self.assertEqual(self.pair("room-detail.html")["room-detail.html"], "/rooms")

    def test_a_project_with_no_specified_pages_pairs_nothing(self):
        (self.project / ".agentforge" / "wireframes" / "wireframes.json").unlink()
        self.assertEqual(self.pair(), {})

    def test_asking_about_one_page_does_not_change_who_owns_a_route(self):
        """Scored over the subset, the confirmation screen took `/rooms/:id`."""
        self.assertEqual(self.pair("booking-confirmation.html"), {})
        self.assertEqual(self.pair("room-detail.html")["room-detail.html"], "/rooms/:id")

    def test_a_route_becomes_the_filename_a_drawing_would_use(self):
        self.assertEqual(prototype_routes.slug_for("/"), "index.html")
        self.assertEqual(prototype_routes.slug_for("/admin/rate-plans/:id"),
                         "admin-rate-plans-id.html")

    def test_only_pages_are_paired(self):
        self.assertEqual(self.pair("styles.css"), {})


if __name__ == "__main__":
    unittest.main()
