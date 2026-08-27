from __future__ import annotations

import unittest

from test import _support  # noqa: F401
from qa_agent.unit.runner import classify
from qa_agent.unit.spec import TIER_ROUTE, select_targets, test_path_for


class UnitTargetSelectionTests(unittest.TestCase):
    def test_route_handler_is_prioritized_over_a_component(self):
        files = {
            "components/RoomCard.jsx": "export default function RoomCard() { return <div /> }",
            "app/api/rooms/route.js": "export async function GET() { return Response.json([]) }",
        }

        targets = select_targets(files, files.get, limit=4)

        self.assertEqual([target.path for target in targets], [
            "app/api/rooms/route.js",
            "components/RoomCard.jsx",
        ])
        self.assertEqual(targets[0].tier, TIER_ROUTE)

    def test_generated_and_module_side_effect_files_are_skipped(self):
        files = {
            "app/page.jsx": "export default function Page() { return null }",
            "lib/mongodb.js": "const client = new MongoClient(); export default client",
            "lib/live.js": "const client = new MongoClient(); export const value = 1",
        }

        self.assertEqual(select_targets(files, files.get), [])

    def test_dynamic_api_route_gets_a_stable_test_path(self):
        self.assertEqual(
            test_path_for("app/api/bookings/[bookingId]/route.js"),
            "tests/unit/api/bookings_bookingId.test.js",
        )

    def test_existing_project_cap_prevents_unbounded_test_generation(self):
        files = {"lib/value.js": "export const value = 1"}

        self.assertEqual(select_targets(files, files.get, already=30), [])

    def test_runner_classifies_actionable_failure_types(self):
        self.assertEqual(classify("Failed to resolve import '@/lib/x'"), "IMPORT")
        self.assertEqual(classify("SyntaxError: Unexpected token"), "SYNTAX")
        self.assertEqual(classify("Test timed out after 5000ms"), "TIMEOUT")
        self.assertEqual(classify("AssertionError: expected 1 to be 2"), "ASSERTION")
        self.assertEqual(classify("socket closed unexpectedly"), "RUNTIME")


if __name__ == "__main__":
    unittest.main()
