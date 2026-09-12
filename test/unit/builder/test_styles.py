"""A drawing keeps its styling even when a page invents a class name.

Tailwind's browser build throws on a class it does not know and then produces
no stylesheet at all, so one `shadow-overlay` in a theme that only declared
`shadow-raised` leaves every page unstyled. That is what happened on a hotel
drawing of seven pages, and what these fix.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from test import _support                                            # noqa: F401
from builder_agent import styles


PAGE = """<!DOCTYPE html>
<html><head>
  <link rel="stylesheet" href="styles.css">
  <script src="tailwind.js"></script>
  <script>
    tailwind.config = {{
      darkMode: 'class',
      theme: {{
        extend: {{
          colors: {{
            primary: 'var(--primary)',
            muted: 'var(--text-muted, #71717A)',
          }},
          boxShadow: {{
            raised: '0 1px 3px rgba(0, 0, 0, 0.08)',
          }},
        }}
      }}
    }}
  </script>
</head>
<body>
  <div class="{classes}">Sagewood House</div>
</body></html>
"""


class DrawingTestCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.folder = self.root / ".agentforge" / "prototype"
        self.folder.mkdir(parents=True)

    def draw(self, classes, *, pages=("index.html",), css="", script=""):
        for name in pages:
            (self.folder / name).write_text(PAGE.format(classes=classes), "utf-8")
        if css:
            (self.folder / "styles.css").write_text(css, "utf-8")
        if script:
            (self.folder / "demo.js").write_text(script, "utf-8")

    def theme(self, page="index.html"):
        return styles.declared((self.folder / page).read_text("utf-8"))


class MissingNameTests(DrawingTestCase):
    def test_a_name_the_theme_never_defined_is_declared(self):
        self.draw("rounded-card p-6 shadow-overlay")
        named = styles.repair(self.root)
        self.assertEqual(sorted(item["name"] for item in named), ["card", "overlay"])
        self.assertIn("overlay", self.theme()["boxShadow"])
        self.assertIn("card", self.theme()["borderRadius"])

    def test_a_name_is_declared_once_and_in_one_family(self):
        self.draw("shadow-overlay")
        named = styles.repair(self.root)
        self.assertEqual([(item["family"], item["name"]) for item in named],
                         [("boxShadow", "overlay")])
        self.assertNotIn("overlay", self.theme()["colors"])

    def test_it_is_declared_on_every_page_of_the_drawing(self):
        pages = ("index.html", "rooms.html", "login.html")
        self.draw("shadow-overlay", pages=pages)
        styles.repair(self.root)
        for page in pages:
            self.assertIn("overlay", self.theme(page)["boxShadow"])

    def test_when_it_is_only_asked_for_on_hover_it_still_counts(self):
        self.draw("shadow-raised hover:shadow-overlay md:rounded-pill")
        styles.repair(self.root)
        self.assertIn("overlay", self.theme()["boxShadow"])
        self.assertIn("pill", self.theme()["borderRadius"])

    def test_a_class_the_pages_own_css_applies_counts_too(self):
        # Where the failure actually came from: Tailwind reported `<css input>`,
        # which was this rule rather than anything in the markup.
        page = PAGE.format(classes="p-4").replace(
            "</head>",
            "<style type='text/tailwindcss'>\n"
            "  .card { @apply bg-surface shadow-raised hover:shadow-overlay; }\n"
            "</style></head>")
        (self.folder / "index.html").write_text(page, "utf-8")
        styles.repair(self.root)
        self.assertIn("overlay", self.theme()["boxShadow"])

    def test_a_class_a_script_adds_counts_too(self):
        self.draw("p-4", script="card.classList.add('bg-surface-alt')")
        styles.repair(self.root)
        self.assertIn("surface-alt", self.theme()["colors"])

    def test_a_family_the_theme_has_none_of_is_made(self):
        self.draw("rounded-card")
        styles.repair(self.root)
        self.assertIn("card", self.theme()["borderRadius"])

    def test_the_design_systems_own_value_is_preferred(self):
        self.draw("shadow-overlay", css=":root { --shadow-overlay: 0 20px 60px #0008; }")
        named = styles.repair(self.root)
        self.assertEqual(named[0]["value"], "var(--shadow-overlay, 0 10px 30px rgba(0, 0, 0, 0.18))")

    def test_the_page_itself_is_not_rewritten(self):
        self.draw("shadow-overlay text-muted")
        styles.repair(self.root)
        page = (self.folder / "index.html").read_text("utf-8")
        self.assertIn('class="shadow-overlay text-muted"', page)


class EngineTests(DrawingTestCase):
    """The drawing renders without the internet, or it is not the drawing checked in."""

    def bundled(self):
        from builder_agent import styles as module
        return Path(module.__file__).resolve().parent / "assets" / "static" / "tailwind.js"

    def test_an_emptied_copy_is_put_back(self):
        self.draw("p-4")
        (self.folder / "tailwind.js").write_text("/* removed - loading from the CDN */", "utf-8")
        self.assertTrue(styles.restore_engine(self.root))
        self.assertEqual((self.folder / "tailwind.js").read_bytes(), self.bundled().read_bytes())

    def test_a_missing_copy_is_put_back(self):
        self.draw("p-4")
        self.assertTrue(styles.restore_engine(self.root))
        self.assertGreater((self.folder / "tailwind.js").stat().st_size, 50_000)

    def test_a_copy_that_is_already_tailwind_is_left_alone(self):
        self.draw("p-4")
        (self.folder / "tailwind.js").write_bytes(self.bundled().read_bytes())
        self.assertFalse(styles.restore_engine(self.root))

    def test_a_drawing_that_never_asked_for_it_gets_nothing(self):
        (self.folder / "index.html").write_text("<html><body>plain</body></html>", "utf-8")
        self.assertFalse(styles.restore_engine(self.root))
        self.assertFalse((self.folder / "tailwind.js").exists())

    def test_a_page_sent_to_the_cdn_is_pointed_home_again(self):
        page = PAGE.format(classes="p-4").replace(
            '<script src="tailwind.js"></script>',
            '<script src="https://cdn.tailwindcss.com"></script>')
        (self.folder / "index.html").write_text(page, "utf-8")
        self.assertTrue(styles.restore_engine(self.root))
        written = (self.folder / "index.html").read_text("utf-8")
        self.assertIn('<script src="tailwind.js"></script>', written)
        # And the CDN stays, as the fallback it was.
        self.assertIn("cdn.tailwindcss.com", written)
        self.assertGreater((self.folder / "tailwind.js").stat().st_size, 50_000)

    def test_the_page_is_left_alone_when_it_already_loads_the_local_copy(self):
        self.draw("p-4")
        (self.folder / "tailwind.js").write_bytes(self.bundled().read_bytes())
        before = (self.folder / "index.html").read_text("utf-8")
        self.assertFalse(styles.restore_engine(self.root))
        self.assertEqual((self.folder / "index.html").read_text("utf-8"), before)


class FadedColourTests(DrawingTestCase):
    """`ring-primary/20` is a class Tailwind cannot make out of `var(--primary)`."""

    def test_a_colour_from_a_variable_is_written_so_it_can_be_faded(self):
        self.draw("focus:ring-primary/20")
        self.assertEqual(styles.alpha_colors(self.root), ["muted", "primary"])
        page = (self.folder / "index.html").read_text("utf-8")
        self.assertIn("color-mix(in srgb, var(--primary) calc(<alpha-value> * 100%), transparent)",
                      page)

    def test_the_variables_own_fallback_is_kept(self):
        self.draw("text-muted/60")
        styles.alpha_colors(self.root)
        page = (self.folder / "index.html").read_text("utf-8")
        self.assertIn("var(--text-muted, #71717A) calc(<alpha-value> * 100%)", page)

    def test_doing_it_twice_changes_nothing_more(self):
        self.draw("ring-primary/20")
        styles.alpha_colors(self.root)
        after = (self.folder / "index.html").read_text("utf-8")
        self.assertEqual(styles.alpha_colors(self.root), [])
        self.assertEqual((self.folder / "index.html").read_text("utf-8"), after)


class LeaveWellAloneTests(DrawingTestCase):
    def test_tailwinds_own_words_are_never_redeclared(self):
        self.draw("shadow-lg rounded-full rounded-t-lg text-center text-2xl border-2 "
                  "bg-white font-bold border-dashed ring-inset bg-no-repeat "
                  "text-slate-500 from-transparent")
        self.assertEqual(styles.repair(self.root), [])

    def test_a_name_the_theme_already_has_is_left_alone(self):
        self.draw("shadow-raised text-primary text-muted")
        self.assertEqual(styles.repair(self.root), [])

    def test_an_arbitrary_value_is_not_a_name(self):
        self.draw("shadow-[0_2px_4px_#000] w-[42rem] text-[#112233]")
        self.assertEqual(styles.repair(self.root), [])

    def test_running_it_again_declares_nothing_new(self):
        self.draw("shadow-overlay text-surface-alt")
        first = styles.repair(self.root)
        self.assertTrue(first)
        self.assertEqual(styles.repair(self.root), [])

    def test_a_drawing_that_is_not_there_is_not_an_error(self):
        with tempfile.TemporaryDirectory() as empty:
            self.assertEqual(styles.repair(Path(empty)), [])


if __name__ == "__main__":
    unittest.main()
