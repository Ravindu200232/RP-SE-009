"""Showing the HTML drawing in the preview, and pointing the camera at it."""
from __future__ import annotations

import unittest
from pathlib import Path

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

    APP, STUDIO, PREFIX = 5173, 7824, "/__agentforge"

    def port(self, route: str) -> int:
        return port_for(route, app_port=self.APP, studio_port=self.STUDIO,
                        prefix=self.PREFIX)

    def test_a_drawing_is_photographed_from_the_studio(self):
        """The iframe's own URL, which is what the studio sends back."""
        self.assertEqual(
            self.port("/__agentforge/api/prototype/hotel/index.html"), self.STUDIO)
        self.assertEqual(
            self.port("/__agentforge/api/prototype/hotel/rooms-id.html"), self.STUDIO)

    def test_an_unprefixed_drawing_route_still_reaches_the_studio(self):
        self.assertEqual(self.port("/prototype/hotel/index.html"), self.STUDIO)

    def test_the_running_application_is_photographed_from_the_dev_server(self):
        for route in ("/", "/rooms", "/admin/orders", "/rooms/12?from=list"):
            self.assertEqual(self.port(route), self.APP, route)

    def test_a_route_that_merely_mentions_a_prototype_is_still_the_app(self):
        """The application is allowed to have its own page about prototypes."""
        for route in ("/prototypes", "/about/prototype", "/blog/prototype-notes",
                      "/__agentforge/api/prototypes"):
            self.assertEqual(self.port(route), self.APP, route)

    def test_a_missing_route_falls_back_to_the_application(self):
        for route in ("", None):
            self.assertEqual(self.port(route), self.APP)


if __name__ == "__main__":
    unittest.main()


class TheDrawingMayServeItsScriptTests(unittest.TestCase):
    """A drawing that cannot serve demo.js is not a drawing anyone can click.

    PROTOTYPE_TYPES listed html, css and images, so every `<script src="demo.js">`
    in every drawing ever shown came back 400. The skill requires that script -
    the basket, the filters, the sign-in and the localStorage that survives a
    walk between pages all live in it - and none of it had ever run in the
    preview. Motion made it visible: a Ferrari drawing whose content waited on an
    IntersectionObserver came up as an empty black page.
    """

    SOURCE = Path("server_modules/builder/projects.py")

    def _types(self):
        # The module has no imports of its own and is exec'd into a prepared
        # namespace, so it is read rather than imported.
        text = self.SOURCE.read_text(encoding="utf-8")
        block = text[text.index("PROTOTYPE_TYPES = {"):]
        return block[:block.index("}") + 1]

    def test_a_drawing_may_serve_its_own_script(self):
        types = self._types()
        self.assertIn('".js"', types)
        self.assertIn("javascript", types)

    def test_the_page_and_the_stylesheet_still_may(self):
        types = self._types()
        self.assertIn('".html"', types)
        self.assertIn('".css"', types)

    def test_the_path_guard_is_still_there(self):
        text = self.SOURCE.read_text(encoding="utf-8")
        self.assertIn("target.relative_to(root)", text)
        self.assertIn("is outside the drawing", text)

    def test_isolate_storage_wraps_safely_and_injects_script(self):
        from server_modules.services.prototype_storage import isolate_storage
        html = b"<!DOCTYPE html><html><head><title>Test</title></head><body><h1>Hello</h1></body></html>"
        injected = isolate_storage(html, "demo-hotel")
        self.assertIn(b"data-agentforge-storage", injected)
        self.assertIn(b"agentforge:prototype:demo-hotel:", injected)
        self.assertIn(b"try {", injected)
