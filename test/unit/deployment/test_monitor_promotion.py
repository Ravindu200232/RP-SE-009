"""A deployment is promoted to LIVE when it is up, not when its review scored well.

The review's build and security categories never change after the deploy, so a
site that scored 88 - an audit finding in a development dependency was enough -
was never promoted however well it served.
"""
from __future__ import annotations

import sys
import unittest

from test import _support

# The deployment agent imports its own packages by their top-level names.
_AGENT = str(_support.ROOT / "deployment-agent" / "deploy_agent")
if _AGENT not in sys.path:
    sys.path.insert(0, _AGENT)

from dfagents.monitor import MonitorAgent  # noqa: E402

ANSWERING = [{"path": "/", "passed": True}, {"path": "/ready", "passed": True}]


def readiness(**categories):
    base = {"build": 0, "cicd": 20, "provider": 25, "security": 8, "monitoring": 10, "api": 10}
    base.update(categories)
    return {"score": sum(base.values()), "categories": base}


class PromotionTests(unittest.TestCase):
    def test_a_serving_site_is_promoted_whatever_the_review_scored(self):
        self.assertTrue(MonitorAgent._serving(readiness(), {"api": ANSWERING}))

    def test_a_failed_workflow_is_not_promoted(self):
        self.assertFalse(MonitorAgent._serving(readiness(cicd=0), {"api": ANSWERING}))

    def test_a_provider_that_is_not_running_it_is_not_promoted(self):
        self.assertFalse(MonitorAgent._serving(readiness(provider=0), {"api": ANSWERING}))

    def test_a_route_that_does_not_answer_is_not_promoted(self):
        failing = [{"path": "/", "passed": True}, {"path": "/ready", "passed": False}]
        self.assertFalse(MonitorAgent._serving(readiness(), {"api": failing}))
        self.assertFalse(MonitorAgent._serving(readiness(), {"api": []}))


if __name__ == "__main__":
    unittest.main()
