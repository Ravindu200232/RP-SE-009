from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from test import _support  # noqa: F401
from deploy_agent.deployment_agent.security import (
    is_secret_name,
    json_dumps_safe,
    redact_data,
    redact_text,
    sha256_bytes,
    sha256_file,
)


class DeploymentSecurityTests(unittest.TestCase):
    def test_secret_names_are_detected_without_hiding_normal_metadata(self):
        self.assertTrue(is_secret_name("AWS_ACCESS_KEY_ID"))
        self.assertTrue(is_secret_name("mongodb_uri"))
        self.assertFalse(is_secret_name("deployment_region"))

    def test_nested_secret_fields_are_redacted_recursively(self):
        payload = {
            "provider": "aws",
            "credentials": {
                "api_key": "value-that-must-not-escape",
                "region": "ap-south-1",
            },
            "steps": [{"token": "hidden"}, {"status": "ready"}],
        }

        redacted = redact_data(payload)

        self.assertEqual(redacted["credentials"]["api_key"], "***REDACTED***")
        self.assertEqual(redacted["steps"][0]["token"], "***REDACTED***")
        self.assertEqual(redacted["credentials"]["region"], "ap-south-1")

    def test_secret_values_embedded_in_log_text_are_redacted(self):
        github_token = "ghp_" + ("x" * 24)
        mongo_uri = "mongodb" + "://user:pass@db.example.test/app"
        message = f"token={github_token} database={mongo_uri}"

        safe = redact_text(message)

        self.assertNotIn(github_token, safe)
        self.assertNotIn(mongo_uri, safe)
        self.assertEqual(safe.count("***REDACTED***"), 2)

    def test_environment_style_secret_line_keeps_the_key_but_hides_the_value(self):
        safe = redact_text("SERVICE_PASSWORD=plain-text-value")

        self.assertEqual(safe, "SERVICE_PASSWORD=***REDACTED***")

    def test_safe_json_never_serializes_nested_credentials(self):
        encoded = json_dumps_safe({"name": "release", "access_token": "do-not-emit"})
        decoded = json.loads(encoded)

        self.assertEqual(decoded, {"name": "release", "access_token": "***REDACTED***"})

    def test_hash_helpers_produce_the_same_artifact_digest(self):
        expected = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        with tempfile.TemporaryDirectory() as tmp:
            artifact = Path(tmp) / "artifact.zip"
            artifact.write_bytes(b"abc")

            self.assertEqual(sha256_bytes(b"abc"), expected)
            self.assertEqual(sha256_file(artifact), expected)

    def test_missing_artifact_has_no_false_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(sha256_file(Path(tmp) / "missing.zip"), "")


if __name__ == "__main__":
    unittest.main()
