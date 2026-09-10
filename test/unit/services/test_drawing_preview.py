"""Showing the HTML drawing in the preview, and pointing the camera at it."""
from __future__ import annotations

import unittest

from test import _support  # noqa: F401
from server_modules.services.shots import port_for


class ShotPortTests(unittest.TestCase):
    """Which server a screenshot is taken from.

    Two different things appear in the same preview pane: the running
    application, served by the dev server, and the HTML drawing of it, served
    by this backend at /prototype/<project>/<file>. The camera is aimed by URL,
    so the port has to follow the route - aimed at the wrong one it photographs
    whatever that port happens to be serving, which is a 404 page, and the user
    gets a picture of an error attached to their message about a button.
    """

    APP, STUDIO = 5173, 7824

    def port(self, route: str) -> int:
        return port_for(route, app_port=self.APP, studio_port=self.STUDIO)

    def test_a_drawing_is_photographed_from_the_studio(self):
        self.assertEqual(self.port("/prototype/hotel/index.html"), self.STUDIO)
        self.assertEqual(self.port("/prototype/hotel/rooms-id.html"), self.STUDIO)

    def test_the_running_application_is_photographed_from_the_dev_server(self):
        for route in ("/", "/rooms", "/admin/orders", "/rooms/12?from=list"):
            self.assertEqual(self.port(route), self.APP, route)

    def test_a_route_that_merely_mentions_a_prototype_is_still_the_app(self):
        """The application is allowed to have its own page about prototypes."""
        for route in ("/prototypes", "/about/prototype", "/blog/prototype-notes"):
            self.assertEqual(self.port(route), self.APP, route)

    def test_a_missing_route_falls_back_to_the_application(self):
        for route in ("", None):
            self.assertEqual(self.port(route), self.APP)


if __name__ == "__main__":
    unittest.main()
