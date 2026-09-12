"""A drawing's photographs are of its subject, not the photo service's stand-in.

LoremFlickr answers a tag set it cannot match with its one default picture, so
every miss on every page was the same photograph - reported as "the same image
on every page".
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test import _support  # noqa: F401
from builder_agent import pictures
from builder_agent.agent import BuilderAgent
from builder_agent.config import Config
from builder_agent.events import Events
from builder_agent.llm import Reply, ToolCall
from test.unit.builder.test_agent_passes import ScriptedRouter

STUDIO = "https://loremflickr.com/800/600/studio,bedroom,minimal?lock=14"


def answers(table):
    """A photo service that answers from a table, and with its stand-in otherwise."""
    return lambda address: table.get(address, "stand-in")


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def page(self, name, *addresses):
        body = "".join(f'<img src="{address}" alt="a room">' for address in addresses)
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"<html><body>{body}</body></html>", encoding="utf-8")
        return path

    def text(self, name):
        return (self.root / name).read_text(encoding="utf-8")

    def test_a_miss_becomes_any_of_its_tags_on_every_page(self):
        self.page("index.html", STUDIO)
        self.page("rooms.html", STUDIO)
        any_of = "https://loremflickr.com/800/600/studio,bedroom,minimal/any?lock=14"
        changed = pictures.repair(self.root, probe=answers({any_of: "photo:1"}))
        self.assertEqual(changed, [(STUDIO, any_of)])
        for name in ("index.html", "rooms.html"):
            self.assertIn(any_of, self.text(name))
            self.assertNotIn(STUDIO, self.text(name))

    def test_then_fewer_tags_and_then_one(self):
        self.page("index.html", STUDIO)
        two = "https://loremflickr.com/800/600/studio,bedroom?lock=14"
        self.assertEqual(pictures.repair(self.root, probe=answers({two: "photo:2"})),
                         [(STUDIO, two)])
        shelf = "https://loremflickr.com/800/600/bookshop,bookshelf?lock=11"
        self.page("books.html", shelf)
        one = "https://loremflickr.com/800/600/bookshop?lock=11"
        self.assertEqual(pictures.repair(self.root, probe=answers({two: "photo:2",
                                                                    one: "photo:3"})),
                         [(shelf, one)])

    def test_an_address_that_cannot_be_checked_is_left_alone(self):
        self.page("index.html", STUDIO)
        self.assertEqual(pictures.repair(self.root, probe=lambda address: ""), [])
        self.assertIn(STUDIO, self.text("index.html"))

    def test_one_photograph_behind_two_addresses_is_not_shown_twice(self):
        first = "https://loremflickr.com/800/600/hotel?lock=1"
        second = "https://loremflickr.com/800/600/hotel?lock=101"
        moved = "https://loremflickr.com/800/600/hotel?lock=118"
        self.page("index.html", first, second)
        changed = pictures.repair(self.root, probe=answers(
            {first: "photo:7", second: "photo:7", moved: "photo:8"}))
        self.assertEqual(changed, [(second, moved)])
        self.assertIn(first, self.text("index.html"))

    def test_the_same_picture_at_two_sizes_is_not_a_photograph_shown_twice(self):
        """A room's card and its detail page ask for one picture at two sizes."""
        card = "https://loremflickr.com/400/300/hotel?lock=11"
        detail = "https://loremflickr.com/800/600/hotel?lock=11"
        self.page("index.html", card)
        self.page("rooms.html", detail)
        self.assertEqual(pictures.repair(self.root, probe=answers(
            {card: "photo:5", detail: "photo:5"})), [])

    def test_a_miss_is_mended_the_same_way_at_every_size(self):
        card = "https://loremflickr.com/400/300/studio,bedroom,minimal?lock=14"
        self.page("index.html", card)
        self.page("rooms.html", STUDIO)
        # Any of the tags finds a card-sized photograph but no big one; two tags
        # find both. Both sizes take two tags, so they stay one photograph.
        card_two = "https://loremflickr.com/400/300/studio,bedroom?lock=14"
        big_two = "https://loremflickr.com/800/600/studio,bedroom?lock=14"
        changed = dict(pictures.repair(self.root, probe=answers({
            "https://loremflickr.com/400/300/studio,bedroom,minimal/any?lock=14": "photo:1",
            card_two: "photo:2", big_two: "photo:2"})))
        self.assertEqual(changed, {card: card_two, STUDIO: big_two})

    def test_a_lock_is_not_mistaken_for_the_start_of_a_longer_one(self):
        one = STUDIO.replace("lock=14", "lock=1")
        twelve = STUDIO.replace("lock=14", "lock=12")
        self.page("index.html", one, twelve)
        any_of = one.replace("minimal?", "minimal/any?")
        pictures.repair(self.root, probe=answers({any_of: "photo:1", twelve: "photo:2"}))
        self.assertIn(any_of, self.text("index.html"))
        self.assertIn(twelve, self.text("index.html"))

    def test_installed_packages_and_hidden_folders_are_not_touched(self):
        for name in ("node_modules/lib/page.html", ".next/page.html", "app/page.jsx"):
            self.page(name, STUDIO)
        any_of = STUDIO.replace("minimal?", "minimal/any?")
        pictures.repair(self.root, probe=answers({any_of: "photo:1"}))
        self.assertIn(any_of, self.text("app/page.jsx"))
        self.assertIn(STUDIO, self.text("node_modules/lib/page.html"))
        self.assertIn(STUDIO, self.text(".next/page.html"))

    def test_line_endings_are_kept(self):
        path = self.root / "index.html"
        path.write_bytes(f'<html>\r\n<img src="{STUDIO}">\r\n</html>\r\n'.encode("utf-8"))
        any_of = STUDIO.replace("minimal?", "minimal/any?")
        pictures.repair(self.root, probe=answers({any_of: "photo:1"}))
        self.assertEqual(path.read_bytes(),
                         f'<html>\r\n<img src="{any_of}">\r\n</html>\r\n'.encode("utf-8"))


class DrawingTests(unittest.TestCase):
    def test_the_drawing_is_shown_with_photographs_of_the_subject(self):
        root = Path(tempfile.mkdtemp())
        agent = BuilderAgent(
            Config(workspace=root, model="scripted", unit_tests=False,
                   e2e_tests=False, state_root=root / ".state"),
            events=Events(), client=object())
        agent.design = {"selection": {
            "palette": "sunset-ember", "paletteName": "Sunset Ember",
            "mood": "Warm.", "themeMode": "light", "font": "grotesk-sharp",
            "typeScale": "comfortable", "radius": "soft", "density": "comfortable",
            "border": "hairline", "elevation": "subtle", "motion": "subtle",
            "tone": "friendly", "contrast": "aa", "container": "1280", "pages": []}}
        agent.screens = [{"id": "/", "route": "/", "label": "Home", "what": "the rooms"}]
        page = (f'<!doctype html><html><head><link rel=stylesheet href=styles.css></head>'
                f'<body><img src="{STUDIO}" alt="The studio room"></body></html>')
        agent.router = ScriptedRouter([
            Reply(calls=[ToolCall("1", "writeFile", {"filePath": ".agentforge/prototype/index.html",
                                                     "content": page})]),
            Reply(content="Drawn.")])
        any_of = STUDIO.replace("minimal?", "minimal/any?")

        with patch.object(pictures, "_http_probe", answers({any_of: "photo:1"})):
            agent.prototype("a small hotel")

        drawn = (root / ".agentforge" / "prototype" / "index.html").read_text(encoding="utf-8")
        self.assertIn(any_of, drawn)
        self.assertNotIn(STUDIO, drawn)


if __name__ == "__main__":
    unittest.main()
