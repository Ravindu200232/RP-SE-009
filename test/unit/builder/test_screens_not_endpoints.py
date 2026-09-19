"""A gateway's API and health routes are endpoints, not screens to draw."""
from __future__ import annotations

import unittest

from test import _support  # noqa: F401
from builder_agent import design


class EndpointsAreNotScreensTests(unittest.TestCase):
    # How a MERN plan names its screens and, beside them, its gateway.
    PLAN = """
## Screens
- `/` — hero, featured books, how the shop works
- `/books` — search by title or author
- `/cart` — line items and a running total

## Runtime
- `/api` — the gateway proxies each service under it
- `/ready` — gateway + three services up on one public port
- `/healthz` — liveness for the platform
"""

    def test_the_api_prefix_and_health_routes_are_not_offered_as_screens(self):
        routes = [page["route"] for page in design.pages_from_plan(self.PLAN)]
        self.assertEqual(routes, ["/", "/books", "/cart"])

    def test_only_the_bare_health_route_is_an_endpoint(self):
        self.assertFalse(design._is_screen("/api"))
        self.assertFalse(design._is_screen("/ready"))
        # A screen that merely shares the word is still a screen.
        self.assertTrue(design._is_screen("/ready-meals"))
        self.assertTrue(design._is_screen("/orders/ready"))


if __name__ == "__main__":
    unittest.main()
