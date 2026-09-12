"""A drawing is not shown to anyone with no styling on it.

Drawings were styled by Tailwind's browser build until one `hover:shadow-overlay`
in a `.card` rule made it throw, and seven pages went out as bare HTML. They
write their own CSS now, which cannot fail that way - an unknown rule is
dropped and the rest of the page keeps its styling. What is left to catch is a
drawing with no stylesheet at all, and it is caught before the user sees it.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from test import _support                                            # noqa: F401
from builder_agent import styles


PAGE = """<!DOCTYPE html>
<html lang="en"><head>
  <meta charset="UTF-8">
  <title>Sagewood House</title>
  {sheet}
</head>
<body><div class="card">Sagewood House</div></body></html>
"""
LINK = '<link rel="stylesheet" href="styles.css">'
STYLESHEET = (":root { --primary: #EA580C; }\n"
              ".card { background: var(--surface); border-radius: var(--radius); }\n"
              * 40)


class DrawingTestCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.folder = self.root / ".agentforge" / "prototype"
        self.folder.mkdir(parents=True)

    def draw(self, *, pages=("index.html",), sheet=LINK, css=STYLESHEET):
        for name in pages:
            (self.folder / name).write_text(PAGE.format(sheet=sheet), "utf-8")
        if css is not None:
            (self.folder / "styles.css").write_text(css, "utf-8")


class ReadingTheFilesTests(DrawingTestCase):
    def test_a_drawing_that_wrote_its_stylesheet_passes(self):
        self.draw(pages=("index.html", "rooms.html"))
        self.assertEqual(styles.unstyled(self.root), [])

    def test_a_page_that_never_links_the_stylesheet_is_bare(self):
        self.draw(pages=("index.html", "rooms.html"), sheet="")
        self.assertEqual(styles.unstyled(self.root), ["index.html", "rooms.html"])

    def test_a_stylesheet_that_was_never_written_leaves_every_page_bare(self):
        self.draw(css=None)
        self.assertEqual(styles.unstyled(self.root), ["index.html"])

    def test_a_stylesheet_of_a_few_lines_is_not_a_stylesheet(self):
        self.draw(css=":root { --primary: #EA580C; }")
        self.assertEqual(styles.unstyled(self.root), ["index.html"])

    def test_a_drawing_that_is_not_there_is_not_a_failure(self):
        with tempfile.TemporaryDirectory() as empty:
            self.assertEqual(styles.unstyled(Path(empty)), [])


class AskingTheBrowserTests(DrawingTestCase):
    """The files can look right while the page still renders bare."""

    def test_a_page_the_browser_applied_nothing_to_is_bare(self):
        self.draw()
        self.assertEqual(styles.unstyled(self.root, lambda page: 0), ["index.html"])

    def test_a_page_the_browser_styled_passes(self):
        self.draw()
        self.assertEqual(styles.unstyled(self.root, lambda page: 120), [])

    def test_no_browser_is_not_a_failure(self):
        self.draw()
        self.assertEqual(styles.unstyled(self.root, lambda page: None), [])

    def test_a_browser_that_will_not_start_is_asked_once_and_let_be(self):
        class Broken:
            def open_tab(self, url="about:blank"):
                asked.append(url)
                raise RuntimeError("no chrome here")

        asked = []
        self.draw(pages=("index.html", "rooms.html", "login.html"))
        look = styles.browser_check(Broken())
        self.assertEqual(styles.unstyled(self.root, look), [])
        self.assertEqual(len(asked), 1)


class NoFrameworkTests(DrawingTestCase):
    def test_the_drawing_no_longer_carries_a_tailwind_build(self):
        # The engine that made one unknown class fatal is not copied in any
        # more; a drawing is its own CSS.
        from builder_agent import agent as agent_module

        source = Path(agent_module.__file__).read_text("utf-8")
        self.assertNotIn("static_tailwind", source)

    def test_the_skill_tells_the_drawing_to_write_its_own_css(self):
        from builder_agent import agent as agent_module

        skill = (Path(agent_module.__file__).resolve().parent / "assets" / "skills"
                 / "html-prototype" / "SKILL.md").read_text("utf-8")
        self.assertIn("No CSS framework", skill)
        self.assertIn("@keyframes", skill)
        self.assertIn("prefers-reduced-motion", skill)


if __name__ == "__main__":
    unittest.main()
