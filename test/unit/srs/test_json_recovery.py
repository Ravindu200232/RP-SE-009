from __future__ import annotations

import unittest

from test import _support  # noqa: F401
from srs_agent.app.llm.json_utils import (
    extract_json,
    format_validation_errors,
    strip_code_fences,
)


class SRSJsonRecoveryTests(unittest.TestCase):
    def test_json_fence_is_removed_before_validation(self):
        raw = '```json\n{"project": "Hotel"}\n```'

        self.assertEqual(strip_code_fences(raw), '{"project": "Hotel"}')
        self.assertEqual(extract_json(raw), {"project": "Hotel"})

    def test_json_object_can_be_recovered_from_explanatory_text(self):
        raw = 'Here is the approved result: {"status": "ready", "questions": []} Done.'

        self.assertEqual(
            extract_json(raw),
            {"status": "ready", "questions": []},
        )

    def test_braces_inside_strings_do_not_break_balanced_object_detection(self):
        raw = 'answer: {"template": "Hello {guest}", "enabled": true} trailing'

        self.assertEqual(
            extract_json(raw),
            {"template": "Hello {guest}", "enabled": True},
        )

    def test_trailing_commas_are_repaired_without_changing_values(self):
        raw = '{"roles": ["guest", "admin",], "complete": true,}'

        self.assertEqual(
            extract_json(raw),
            {"roles": ["guest", "admin"], "complete": True},
        )

    def test_empty_or_non_object_responses_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "empty LLM response"):
            extract_json("   ")
        with self.assertRaisesRegex(ValueError, "could not parse JSON"):
            extract_json('["not", "an", "object"]')

    def test_validation_errors_are_compact_and_keep_field_paths(self):
        errors = [
            {"loc": ["project", "name"], "msg": "Field required"},
            {"loc": ["roles", 0, "name"], "msg": "Must be text"},
        ]

        message = format_validation_errors(errors)

        self.assertIn("project.name: Field required", message)
        self.assertIn("roles.0.name: Must be text", message)


if __name__ == "__main__":
    unittest.main()
