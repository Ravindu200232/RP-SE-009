"""What a run changed, recovered from the snapshot it started from.

The transaction that follows a run used to be handed one sentence about it.
These tests hold the other half to its promises: that the files named are the
files that moved, that a page nobody touched is absent, that one role's work is
not reported as another's, and that a diff cut short says so rather than
passing itself off as the whole change.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from test._support import ROOT  # noqa: F401 - puts the repository on sys.path

from server_modules.services import change_set


class ChangeSetTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.project = Path(temporary.name) / "app"
        self.prototype = self.project / ".agentforge" / "prototype"
        self.prototype.mkdir(parents=True)
        self.store = self.project / ".agentforge" / "undo" / "snap" / "files"

    def before(self, relative: str, text: str) -> None:
        """A file as the snapshot found it."""
        path = self.store / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def now(self, relative: str, text: str) -> None:
        """A file as the run left it."""
        path = self.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_an_edited_page_is_named_and_shown(self):
        self.before(".agentforge/prototype/index.html", "<h1>Rooms</h1>\n")
        self.now(".agentforge/prototype/index.html", "<h1>Our rooms</h1>\n")
        change = change_set.capture(self.project, "snap", "designer")
        self.assertEqual(change["files"],
                         [{"path": ".agentforge/prototype/index.html", "kind": "modified"}])
        self.assertIn("-<h1>Rooms</h1>", change["diff"])
        self.assertIn("+<h1>Our rooms</h1>", change["diff"])
        self.assertFalse(change["truncated"])

    def test_a_page_the_run_added_is_recorded_as_added(self):
        self.before(".agentforge/prototype/index.html", "<h1>Rooms</h1>\n")
        self.now(".agentforge/prototype/index.html", "<h1>Rooms</h1>\n")
        self.now(".agentforge/prototype/book.html", "<h1>Book</h1>\n")
        change = change_set.capture(self.project, "snap", "designer")
        self.assertEqual([row["path"] for row in change["files"]],
                         [".agentforge/prototype/book.html"])
        self.assertEqual(change["files"][0]["kind"], "added")

    def test_a_page_the_run_deleted_is_recorded_as_deleted(self):
        self.before(".agentforge/prototype/old.html", "<h1>Old</h1>\n")
        change = change_set.capture(self.project, "snap", "designer")
        self.assertEqual(change["files"], [{"path": ".agentforge/prototype/old.html",
                                            "kind": "deleted"}])

    def test_a_page_nobody_touched_is_not_a_change(self):
        """The reader is a model: a file listed for nothing is a file it reads for nothing."""
        self.before(".agentforge/prototype/index.html", "<h1>Rooms</h1>\n")
        self.now(".agentforge/prototype/index.html", "<h1>Rooms</h1>\n")
        change = change_set.capture(self.project, "snap", "designer")
        self.assertEqual(change["files"], [])
        self.assertEqual(change["diff"], "")

    def test_the_build_change_is_not_the_drawing_change(self):
        """The developer's files are the application's; the prototype is not among them."""
        self.before("app/page.jsx", "export default () => <p>a</p>\n")
        self.now("app/page.jsx", "export default () => <p>b</p>\n")
        self.now(".agentforge/prototype/index.html", "<h1>untouched by the build</h1>\n")
        change = change_set.capture(self.project, "snap", "developer")
        self.assertEqual([row["path"] for row in change["files"]], ["app/page.jsx"])

    def test_a_long_diff_admits_that_it_was_shortened(self):
        self.before(".agentforge/prototype/index.html", "".join(f"<p>{n}</p>\n" for n in range(4000)))
        self.now(".agentforge/prototype/index.html", "".join(f"<p>x{n}</p>\n" for n in range(4000)))
        change = change_set.capture(self.project, "snap", "designer")
        self.assertTrue(change["truncated"])
        self.assertLessEqual(len(change["diff"]), change_set.MAX_DIFF_CHARS + 200)
        self.assertIn("shortened", change_set.brief(change))

    def test_a_change_with_no_files_has_nothing_to_say(self):
        self.assertEqual(change_set.brief({"files": []}), "")
        self.assertEqual(change_set.brief({}), "")

    def test_a_brief_names_the_files_and_shows_the_diff(self):
        self.before(".agentforge/prototype/index.html", "<h1>Rooms</h1>\n")
        self.now(".agentforge/prototype/index.html", "<h1>Our rooms</h1>\n")
        text = change_set.brief(change_set.capture(self.project, "snap", "designer"))
        self.assertIn(".agentforge/prototype/index.html (modified)", text)
        self.assertIn("```diff", text)

    def test_a_hand_edit_is_the_same_shape_as_a_run(self):
        change = change_set.from_edit(".agentforge/prototype/index.html",
                                      "<h1>Rooms</h1>\n", "<h1>Our rooms</h1>\n")
        self.assertEqual(change["files"], [{"path": ".agentforge/prototype/index.html",
                                            "kind": "modified"}])
        self.assertIn("+<h1>Our rooms</h1>", change["diff"])

    def test_a_hand_edit_that_changed_nothing_is_not_a_change(self):
        self.assertEqual(change_set.from_edit("a.html", "<p>same</p>", "<p>same</p>"), {})

    def test_a_carried_change_is_forgotten(self):
        """Left behind, it would be shown to the next run as its own work."""
        change_set.write(self.project, "designer", {"files": [{"path": "a.html", "kind": "added"}]})
        self.assertTrue(change_set.read(self.project, "designer"))
        change_set.clear(self.project, "designer")
        self.assertEqual(change_set.read(self.project, "designer"), {})

    def test_only_the_prototype_pages_are_asked_for(self):
        change = {"files": [{"path": ".agentforge/prototype/index.html", "kind": "modified"},
                            {"path": ".agentforge/prototype/styles.css", "kind": "modified"},
                            {"path": "app/page.jsx", "kind": "modified"}]}
        self.assertEqual(change_set.touched(change, under=".agentforge/prototype/"),
                         [".agentforge/prototype/index.html", ".agentforge/prototype/styles.css"])


if __name__ == "__main__":
    unittest.main()
