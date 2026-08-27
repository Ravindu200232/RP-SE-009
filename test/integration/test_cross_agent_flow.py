from __future__ import annotations

import json
import unittest

from test import _support  # noqa: F401
from deploy_agent.deployment_agent.security import json_dumps_safe
from qa_agent.unit.spec import TIER_ROUTE, select_targets
from srs_agent.app.generators.builder_utils import _api_file, _normal_route_pattern


class CrossAgentFlowTests(unittest.TestCase):
    def test_srs_dynamic_api_handoff_is_testable_by_the_qa_agent(self):
        approved_route = _normal_route_pattern("/api/bookings/{booking_id}")
        generated_file = _api_file(approved_route)
        generated_source = (
            "export async function PATCH(request, context) { "
            "return Response.json({ id: context.params.booking_id }) }"
        )

        targets = select_targets(
            [generated_file],
            lambda path: generated_source if path == generated_file else None,
        )

        self.assertEqual(generated_file, "app/api/bookings/[booking_id]/route.js")
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0].tier, TIER_ROUTE)
        self.assertEqual(targets[0].test_path, "tests/unit/api/bookings_booking_id.test.js")

    def test_deployment_receipt_can_include_handoff_metadata_without_leaking_secrets(self):
        handoff = {
            "project": "sample-app",
            "source": "builder",
            "deployment": {
                "provider": "aws",
                "access_key": "must-stay-private",
                "status": "ready",
            },
        }

        receipt = json.loads(json_dumps_safe(handoff))

        self.assertEqual(receipt["project"], "sample-app")
        self.assertEqual(receipt["deployment"]["provider"], "aws")
        self.assertEqual(receipt["deployment"]["status"], "ready")
        self.assertEqual(receipt["deployment"]["access_key"], "***REDACTED***")

    def test_repository_contains_each_full_app_subsystem(self):
        expected = [
            "agents",
            "qa_agent",
            "srs-agent",
            "deployment-agent",
            "server_modules",
            "studio",
            "desktop",
        ]

        missing = [name for name in expected if not (_support.ROOT / name).is_dir()]

        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
