"""Pointing at something in the preview, and what the agent is told about it."""
from __future__ import annotations

import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from test import _support  # noqa: F401
import server_runtime as server
from server_modules.services.shots import _clip, ink_bounds


def resolved(path: str, line: int = 0):
    return types.SimpleNamespace(path=path, line=line, used_model=False)


class AttachmentShapeTests(unittest.TestCase):
    def test_one_element_or_many_arrive_the_same_way(self):
        """The old contract sent a bare dict; the studio now sends a list."""
        self.assertEqual(server._as_list({"tag": "button"}), [{"tag": "button"}])
        self.assertEqual(server._as_list([{"a": 1}, {"b": 2}]), [{"a": 1}, {"b": 2}])
        self.assertEqual(server._as_list(None), [])
        self.assertEqual(server._as_list([None, {}, {"c": 3}]), [{"c": 3}])

    def test_a_data_uri_is_unwrapped_before_it_reaches_the_model(self):
        """The browser needs the `data:` prefix to render it; Ollama chokes on it."""
        self.assertEqual(
            server._image_of({"image": "data:image/jpeg;base64,QUJD"}), "QUJD")
        self.assertEqual(server._image_of({"image": "QUJD"}), "QUJD")
        self.assertEqual(server._image_of("QUJD"), "QUJD")
        self.assertEqual(server._image_of({}), "")

    def test_a_drawing_is_told_apart_from_a_click(self):
        self.assertEqual(server._kind_of({"kind": "drawing"}), "drawing")
        self.assertEqual(server._kind_of({"image": "x"}), "element")


class SelectionBriefTests(unittest.TestCase):
    def brief(self, found, pictures=(), prompt="make it tighter", route="/plants",
              page_file=""):
        return server._selection_brief(list(found), list(pictures), prompt,
                                       route, page_file, "model")

    def test_every_selected_element_names_the_file_that_renders_it(self):
        text = self.brief([
            ({"tag": "button", "text": "Add to basket"}, resolved("app/plants/page.jsx", 42)),
            ({"tag": "h1", "text": "Our plants"}, resolved("components/Head.jsx")),
        ])
        self.assertIn("app/plants/page.jsx", text)
        self.assertIn("around line 42", text)
        self.assertIn("components/Head.jsx", text)
        self.assertIn("these elements", text)      # plural, because there are two
        self.assertIn("make it tighter", text)

    def test_one_element_is_not_described_in_the_plural(self):
        text = self.brief([({"tag": "button"}, resolved("app/page.jsx"))])
        self.assertIn("this element", text)
        self.assertNotIn("these elements", text)

    def test_a_drawing_says_what_the_red_line_means(self):
        text = self.brief([], [{"kind": "drawing", "image": "AAAA"}],
                          page_file="app/plants/page.jsx")
        self.assertIn("red line", text)
        self.assertIn("app/plants/page.jsx", text)
        self.assertIn(server.PENCIL_SYSTEM.split("\n")[0], text)

    def test_a_click_uses_the_element_contract_not_the_drawing_one(self):
        text = self.brief([({"tag": "button"}, resolved("app/page.jsx"))])
        self.assertIn(server.ELEMENT_EDIT_SYSTEM.split("\n")[0], text)
        self.assertNotIn("red line", text)

    def test_a_model_that_cannot_see_says_so_instead_of_dropping_the_picture(self):
        """Half a request silently ignored is worse than a request that admits it."""
        original = server.ollama
        server.ollama = types.SimpleNamespace(supports_vision=lambda model: False)
        try:
            text = self.brief([({"tag": "button"}, resolved("app/page.jsx"))],
                              [{"kind": "element", "image": "AAAA"}])
        finally:
            server.ollama = original
        self.assertIn("cannot see", text)

    def test_what_the_screenshot_shows_is_folded_into_the_brief(self):
        seen = []
        original = server.ollama

        def chat(model, messages, **kw):
            seen.append(messages[-1]["images"])
            return {"message": {"content": "A cramped card with no gap above the price."}}

        server.ollama = types.SimpleNamespace(
            supports_vision=lambda model: True, chat=chat)
        try:
            text = self.brief([({"tag": "div"}, resolved("app/page.jsx"))],
                              [{"kind": "element", "image": "data:image/jpeg;base64,QUJD"}])
        finally:
            server.ollama = original
        self.assertEqual(seen, [["QUJD"]])          # unwrapped, once
        self.assertIn("no gap above the price", text)


class PointedAtTests(unittest.TestCase):
    """What was pointed at is named to the model, and to nobody else."""

    def test_a_selection_is_named_as_this_section_or_sections(self):
        self.assertEqual(server._pointed_at("make it red", [{"tag": "header"}], []),
                         "make it red (this section or sections)")

    def test_a_drawing_is_named_as_this_image(self):
        self.assertEqual(server._pointed_at("make it bigger", [], [{"kind": "drawing"}]),
                         "make it bigger (this image)")
        self.assertEqual(server._pointed_at("fix it", [{"tag": "div"}], [{"kind": "drawing"}]),
                         "fix it (this section or sections and this image)")

    def test_the_photograph_of_a_click_is_not_a_drawing(self):
        self.assertEqual(server._pointed_at("fix it", [{"tag": "div"}],
                                            [{"kind": "element", "image": "x"}]),
                         "fix it (this section or sections)")

    def test_the_model_hears_it_and_the_studio_does_not(self):
        logged = []
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(server, "_workspace", return_value=Path(directory)), \
                patch.object(server, "_edit_run") as run, \
                patch.object(server, "elog", side_effect=lambda level, text: logged.append(text)), \
                patch.object(server, "eprog"), patch.object(server, "emit"):
            server.run_element_edit("shop", "make it red", [{"tag": "header", "text": "Shop"}],
                                    "model", shots=[{"kind": "drawing"}], route="/")
        self.assertEqual(run.call_args.args[1], "make it red")
        self.assertIn("make it red (this section or sections and this image)",
                      run.call_args.kwargs["brief"])
        self.assertFalse([line for line in logged if "this section" in line or "this image" in line])


class ScreenshotGeometryTests(unittest.TestCase):
    def test_an_element_box_is_taken_in_page_coordinates(self):
        """getBoundingClientRect is viewport-relative; the clip is not."""
        clip = _clip({"x": 100, "y": 40, "w": 300, "h": 80},
                     {"x": 0, "y": 500})
        self.assertEqual(clip["x"], 100 - 14)
        self.assertEqual(clip["y"], 40 + 500 - 14)
        self.assertEqual(clip["width"], 300 + 28)

    def test_a_box_at_the_top_left_is_not_pushed_off_the_page(self):
        clip = _clip({"x": 2, "y": 1, "w": 300, "h": 80}, {})
        self.assertEqual((clip["x"], clip["y"]), (0.0, 0.0))

    def test_a_tiny_element_still_gets_a_readable_photograph(self):
        clip = _clip({"x": 10, "y": 10, "w": 8, "h": 8}, {})
        self.assertGreaterEqual(clip["width"], 120)
        self.assertGreaterEqual(clip["height"], 60)

    def test_a_drawing_is_photographed_with_room_around_it(self):
        box = ink_bounds([[{"x": 200, "y": 300}, {"x": 640, "y": 700}]])
        self.assertEqual(box["x"], 200 - 24)
        self.assertEqual(box["y"], 300 - 24)
        self.assertEqual(box["width"], 440 + 48)

    def test_a_stray_click_is_not_a_drawing(self):
        self.assertEqual(ink_bounds([]), {})
        self.assertEqual(ink_bounds([[]]), {})


if __name__ == "__main__":
    unittest.main()
