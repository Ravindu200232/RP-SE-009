"""A project's app, reachable from somewhere other than this machine.

A preview answers on p-<hash>.localhost because the generated app asks for
everything from the root. That name means nothing on a phone, so a studio
opened away from this machine gets an address of its own for the app - one
tunnel per project, told which preview host its requests are for.
"""
from __future__ import annotations

import threading
import unittest
from unittest import mock

from test import _support                                            # noqa: F401
from server_modules.services import preview_link
from server_modules.services.preview_link import PreviewLinks


class FakeTunnel:
    """The slice of a cloudflared process that matters here."""

    def __init__(self, lines, alive=True):
        self.lines = list(lines)
        self.alive = alive
        self.ended = False
        self.closed = threading.Event()
        self.stdout = self._read()

    def _read(self):
        for line in self.lines:
            yield line
        # A real tunnel keeps its pipe open until it is stopped.
        self.closed.wait(10)

    def poll(self):
        return None if self.alive and not self.ended else 0

    def terminate(self):
        self.ended = True
        self.alive = False
        self.closed.set()

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.terminate()


ANNOUNCEMENT = [
    "INF Requesting new quick Tunnel on trycloudflare.com...",
    "INF |  https://four-random-words-here.trycloudflare.com  |",
    "INF Connection registered connIndex=0",
]


class PublishingTests(unittest.TestCase):
    def setUp(self):
        self.started = []

        def spawn(program, host):
            tunnel = FakeTunnel(ANNOUNCEMENT)
            self.started.append({"program": program, "host": host, "proc": tunnel})
            return tunnel

        self.links = PreviewLinks(port=7824, spawn=spawn, ready_seconds=5)
        self.addCleanup(self.links.close_all)

    def test_an_unpublished_preview_has_no_address(self):
        self.assertEqual(self.links.url("p-abc.localhost"), "")

    def test_publishing_answers_with_the_address_the_tunnel_printed(self):
        url = self.links.open("p-abc.localhost")
        self.assertEqual(url, "https://four-random-words-here.trycloudflare.com")
        self.assertEqual(self.links.url("p-abc.localhost"), url)

    def test_the_tunnel_is_told_which_preview_it_is_for(self):
        self.links.open("p-abc.localhost")
        self.assertEqual(self.started[0]["host"], "p-abc.localhost")

    def test_publishing_twice_keeps_the_one_address(self):
        first = self.links.open("p-abc.localhost")
        self.assertEqual(self.links.open("p-abc.localhost"), first)
        self.assertEqual(len(self.started), 1)

    def test_two_projects_are_published_separately(self):
        self.links.open("p-abc.localhost")
        self.links.open("p-def.localhost")
        self.assertEqual([item["host"] for item in self.started],
                         ["p-abc.localhost", "p-def.localhost"])

    def test_closing_takes_the_address_away_and_stops_the_tunnel(self):
        self.links.open("p-abc.localhost")
        self.links.close("p-abc.localhost")
        self.assertEqual(self.links.url("p-abc.localhost"), "")
        self.assertTrue(self.started[0]["proc"].ended)

    def test_a_tunnel_that_died_no_longer_counts_as_an_address(self):
        self.links.open("p-abc.localhost")
        self.started[0]["proc"].alive = False
        self.assertEqual(self.links.url("p-abc.localhost"), "")

    def test_shutting_down_stops_every_tunnel(self):
        self.links.open("p-abc.localhost")
        self.links.open("p-def.localhost")
        self.links.close_all()
        self.assertTrue(all(item["proc"].ended for item in self.started))

    def test_two_requests_at_once_publish_one_address(self):
        seen, barrier = [], threading.Barrier(2)

        def publish():
            barrier.wait(timeout=5)
            seen.append(self.links.open("p-abc.localhost"))

        threads = [threading.Thread(target=publish) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        self.assertEqual(len(set(seen)), 1)
        self.assertEqual(self.links.url("p-abc.localhost"), seen[0])
        # Whichever tunnel lost the race is not left running.
        self.assertEqual(sum(1 for item in self.started if not item["proc"].ended), 1)


class NotPublishableTests(unittest.TestCase):
    def test_a_tunnel_that_says_nothing_is_not_left_running(self):
        started = []

        def spawn(program, host):
            tunnel = FakeTunnel(["INF starting", "INF still starting"])
            started.append(tunnel)
            return tunnel

        links = PreviewLinks(port=7824, spawn=spawn, ready_seconds=0.3)
        with self.assertRaises(ValueError):
            links.open("p-abc.localhost")
        self.assertTrue(started[0].ended)
        self.assertEqual(links.url("p-abc.localhost"), "")

    def test_without_the_program_it_says_so_instead_of_failing_oddly(self):
        links = PreviewLinks(port=7824)
        with mock.patch.object(preview_link, "cloudflared", return_value=""):
            with self.assertRaises(ValueError) as refused:
                links.open("p-abc.localhost")
        self.assertIn("cloudflared", str(refused.exception))


if __name__ == "__main__":
    unittest.main()
