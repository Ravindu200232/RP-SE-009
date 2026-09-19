"""A page reduced to the part a wireframe is drawn from.

Twelve kilobytes of markup will not fit beside a specification in an
eight-thousand token window, and most of it - the font link, the class lists,
the script that fills a table - says nothing about what the page looks like.
What has to survive the reduction is the order of the sections, the headings,
the controls and the page's own words; what has to disappear is everything
else, including the wrapper divs that would otherwise spend the whole depth
budget before reaching any content.
"""
from __future__ import annotations

import unittest

from test._support import ROOT  # noqa: F401 - puts the repository on sys.path

from server_modules.services import page_outline

PAGE = """<!DOCTYPE html>
<html><head><title>Rooms - Hotel Indoora</title>
<link rel="stylesheet" href="styles.css">
<style>.hero { color: red }</style></head>
<body>
  <header id="navbar"><nav class="nav-links"><a>Home</a><a>Rooms</a></nav></header>
  <main>
    <div><div><section class="hero">
      <h1>Our rooms</h1>
      <p class="lead">Every room faces the courtyard.</p>
      <img src="hero.jpg" alt="The courtyard">
      <a class="btn">Book now</a>
    </section></div></div>
    <form><input type="email" placeholder="Your email"><button>Send</button></form>
  </main>
  <script>document.querySelector('h1').textContent = 'never read'</script>
</body></html>"""


class OutlineTests(unittest.TestCase):
    def setUp(self):
        self.outline = page_outline.outline(PAGE)

    def test_the_sections_keep_their_order(self):
        positions = [self.outline.index(part) for part in
                     ("header#navbar", "section.hero", 'h1 "Our rooms"', "form")]
        self.assertEqual(positions, sorted(positions))

    def test_an_element_keeps_its_name_and_its_words(self):
        self.assertIn('h1 "Our rooms"', self.outline)
        self.assertIn('a.btn "Book now"', self.outline)

    def test_a_field_keeps_what_it_asks_for(self):
        self.assertIn('input [email] "Your email"', self.outline)

    def test_an_image_is_named_by_what_it_shows(self):
        self.assertIn('img "The courtyard"', self.outline)

    def test_presentation_and_behaviour_do_not_survive(self):
        for gone in ("stylesheet", "styles.css", "color: red", "never read", "<"):
            self.assertNotIn(gone, self.outline)

    def test_an_unnamed_wrapper_does_not_cost_a_level(self):
        """Four wrapper divs deep is how an outline runs out of depth before content."""
        self.assertLess(self.outline.index("section.hero") - self.outline.index("main"), 10)

    def test_a_repeated_row_is_recorded_once_and_counted(self):
        rows = "".join('<li class="row"><span>item</span></li>' for _ in range(9))
        self.assertIn("(x9)", page_outline.outline(f"<ul>{rows}</ul>"))

    def test_the_outline_is_small_enough_to_put_in_a_prompt(self):
        self.assertLessEqual(len(page_outline.outline(PAGE * 40)), page_outline.MAX_CHARS + 4)

    def test_broken_markup_yields_what_was_read_rather_than_an_error(self):
        self.assertIn('h1 "Half"', page_outline.outline("<main><h1>Half</h1><sect"))

    def test_nothing_at_all_is_not_an_outline(self):
        self.assertEqual(page_outline.outline(""), "")

    def test_the_title_is_readable_on_its_own(self):
        self.assertEqual(page_outline.title_of(PAGE), "Rooms - Hotel Indoora")


if __name__ == "__main__":
    unittest.main()
