"""The seams between the four agents.

Each agent is tested on its own elsewhere. What matters here is that what one
hands to the next is something the next can actually use: a route the SRS
approved has to be a route the QA agent can reach, and a deployment receipt has
to survive being written down without carrying a secret with it.
"""
from __future__ import annotations

import json
import unittest

from test import _support  # noqa: F401
from builder_agent.config import detect_stack, stack_for
from deploy_agent.deployment_agent.security import json_dumps_safe
from qa_agent import e2e as qa_e2e
from srs_agent.app.generators.builder_utils import _api_file, _normal_route_pattern


class CrossAgentFlowTests(unittest.TestCase):
    def test_an_approved_dynamic_route_is_a_route_the_qa_agent_can_drive(self):
        """The SRS names a route; the builder files it; the QA agent reaches it.

        The dynamic segment is where this used to break: the specification
        writes `{booking_id}` and the App Router wants `[booking_id]`, so a
        mismatch here means every generated journey 404s.
        """
        approved = _normal_route_pattern("/api/bookings/{booking_id}")
        generated = _api_file(approved)

        self.assertEqual(generated, "app/api/bookings/[booking_id]/route.js")

        # The QA agent records the journey that exercised it; the studio then
        # renders that as stages. Both sides have to agree on the shape.
        evidence = {"suites": [{
            "kind": "e2e", "suite": "booking detail", "status": "passed",
            "output": "1. navigate -> /bookings/1\n2. assert textIncludes",
        }]}
        journey = qa_e2e.journeys_from_evidence(evidence)[0]

        self.assertEqual(journey.score()["stage_total"], 2)
        self.assertEqual(journey.score()["stage_passed"], 2)

    def test_a_failed_journey_reports_where_it_broke_not_just_that_it_broke(self):
        evidence = {"suites": [{
            "kind": "e2e", "suite": "checkout", "status": "failed",
            "reason": "Step 3 failed: no Pay button",
            "output": "1. navigate -> /cart\n2. click Add\n3. click Pay\n4. assert textIncludes",
        }]}
        journey = qa_e2e.journeys_from_evidence(evidence)[0]
        score = journey.score()

        self.assertEqual(score["stage_passed"], 2)
        self.assertEqual(score["stage_failed"], 1)
        # Never executed, so never reported as failed: that would both
        # overstate the damage and hide where the break actually is.
        self.assertEqual(score["stage_not_reached"], 1)

    def test_the_builder_stack_is_product_owned_not_model_chosen(self):
        self.assertEqual(detect_stack("build a hotel booking site"), "nextjs-mongo")
        self.assertEqual(detect_stack("a MERN microservices shop"), "mern-microservices")
        # An unknown id can never move a build off a supported stack.
        self.assertEqual(stack_for("django-postgres").id, "nextjs-mongo")

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
            "builder-agent",
            "qa-agent",
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
