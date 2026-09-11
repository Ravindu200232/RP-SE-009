"""The specification and the deployment plan always use one model, whatever the
studio's picker saved; the picker is for the build. And the monitor asks the
health route the plan names, not a Next.js one every app is assumed to have."""
from __future__ import annotations

import sys
import unittest
from unittest import mock

from test import _support

# The deployment agent imports its own packages by their top-level names.
_AGENT = str(_support.ROOT / "deployment-agent" / "deploy_agent")
if _AGENT not in sys.path:
    sys.path.insert(0, _AGENT)

from deploy_agent import bridge as deploy_bridge  # noqa: E402
from dfagents.monitor import MonitorAgent  # noqa: E402
from srs_agent import bridge as srs_bridge  # noqa: E402

# What the picker used to write for every role at once.
PICKED_FOR_THE_BUILD = {
    "agent_model": "glm-5.3-flash:cloud",
    "srs_model": "glm-5.3-flash:cloud",
    "deploy_model": "glm-5.3-flash:cloud",
}


class FixedModelTests(unittest.TestCase):
    def test_the_deployment_plan_is_written_by_gemma_whatever_was_saved(self):
        with mock.patch.object(deploy_bridge, "agentforge_settings", return_value=dict(PICKED_FOR_THE_BUILD)):
            self.assertEqual(deploy_bridge.deploy_model(), "gemma4:31b-cloud")

    def test_the_specification_is_written_by_gemma_whatever_was_saved(self):
        with mock.patch.object(srs_bridge, "agentforge_settings", return_value=dict(PICKED_FOR_THE_BUILD)):
            self.assertEqual(srs_bridge.srs_model(), "gemma4:31b-cloud")


class _Response:
    """The slice of requests.Response the monitor reads."""

    status_code = 200

    class elapsed:  # noqa: N801
        @staticmethod
        def total_seconds():
            return 0.01


class HealthProbeTests(unittest.TestCase):
    def test_the_monitor_asks_the_health_route_the_plan_names(self):
        asked = []

        def get(url, **_kwargs):
            asked.append(url)
            return _Response()

        with mock.patch("requests.get", get):
            results = MonitorAgent._validate_api("http://app.example", "/ready")

        self.assertEqual(asked, ["http://app.example/", "http://app.example/ready"])
        self.assertTrue(all(item["passed"] for item in results))

    def test_a_plan_without_a_health_route_keeps_the_nextjs_one(self):
        asked = []

        def get(url, **_kwargs):
            asked.append(url)
            return _Response()

        with mock.patch("requests.get", get):
            MonitorAgent._validate_api("http://app.example")

        self.assertEqual(asked, ["http://app.example/", "http://app.example/api/health"])


if __name__ == "__main__":
    unittest.main()
