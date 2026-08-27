from __future__ import annotations

import ast
import re
import unittest

from test import _support
from test._support import FakeDaemon, cloud_entry, fake_ollama
from agents.core.ollama_client import (CLOUD_DEFAULT_CTX, FALLBACK_CLOUD,
                                       LOCAL_DEFAULT_CTX, is_cloud_model,
                                       max_context)


ROOT = _support.ROOT
MODELS_JS = ROOT / "studio" / "lib" / "models.js"
HTTP_HANDLER = ROOT / "server_modules" / "ui" / "http_handler.py"


def string_default(relative_path: str, name: str) -> str:
    """
    The literal a module assigns to `name`, ignoring any env override.

    Reading the source rather than importing keeps the assertion about what
    ships: a developer with `DEPLOYMENT_AGENT_MODEL` exported would otherwise
    silently test their own machine instead of the default.
    """
    source = (ROOT / relative_path).read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            continue
        value = node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            return value.value
        # `os.environ.get("VAR", "default")`
        if isinstance(value, ast.Call) and len(value.args) == 2:
            fallback = value.args[1]
            if isinstance(fallback, ast.Constant):
                return str(fallback.value)
    raise AssertionError(f"{relative_path} does not assign a string to {name}")


def studio_catalogue_keys() -> set[str]:
    """Every `p.<key>` the studio's `catalogue()` reads off the payload."""
    source = MODELS_JS.read_text(encoding="utf-8")
    start = source.index("export function catalogue(")
    end = source.index("\n}", start)
    return set(re.findall(r"\bp\.([a-z_]+)", source[start:end]))


def studio_label_keys() -> set[str]:
    """The model ids the studio renames for display."""
    source = MODELS_JS.read_text(encoding="utf-8")
    start = source.index("const CLOUD_UI_LABELS")
    end = source.index("}", start)
    return set(re.findall(r"'([^']+)'\s*:", source[start:end]))


class CataloguePayloadContractTests(unittest.TestCase):
    def test_the_studio_reads_only_catalogue_keys_the_backend_emits(self):
        daemon = FakeDaemon()

        with fake_ollama(daemon) as client:
            emitted = set(client.catalog())

        self.assertEqual(studio_catalogue_keys() - emitted, set())

    def test_the_catalogue_reports_the_daemon_as_ready_only_when_it_answers(self):
        running = FakeDaemon()
        with fake_ollama(running) as client:
            self.assertTrue(client.catalog()["ollama_ready"])

        stopped = FakeDaemon(reachable=False)
        with fake_ollama(stopped) as client:
            self.assertFalse(client.catalog()["ollama_ready"])

    def test_the_models_and_settings_endpoints_agree_on_cloud_readiness(self):
        # /settings once answered `bool(key)`, so a signed-in daemon with no
        # key was cloud-enabled on one endpoint and cloud-off on the other.
        source = HTTP_HANDLER.read_text(encoding="utf-8")

        readiness = re.findall(r'"cloud_enabled":\s*([^,\n]+)', source)

        self.assertTrue(readiness, "http_handler reports no cloud_enabled")
        for expression in readiness:
            self.assertIn("cloud_ready()", expression)


class AgentModelDefaultTests(unittest.TestCase):
    def test_the_agent_defaults_are_models_the_catalogue_can_offer(self):
        defaults = {
            "srs-agent/srs_agent/bridge.py": "DEFAULT_SRS_MODEL",
            "deployment-agent/deploy_agent/bridge.py": "DEFAULT_DEPLOY_MODEL",
            "deployment-agent/deploy_agent/deployment_agent/config.py": "OLLAMA_MODEL",
        }

        for path, name in defaults.items():
            with self.subTest(module=path):
                self.assertIn(string_default(path, name), FALLBACK_CLOUD)

    def test_every_known_cloud_model_routes_as_cloud_before_it_is_pulled(self):
        daemon = FakeDaemon()

        with fake_ollama(daemon):
            not_cloud = [m for m in FALLBACK_CLOUD if not is_cloud_model(m)]

        self.assertEqual(not_cloud, [])

    def test_every_studio_cloud_label_names_a_model_the_backend_calls_cloud(self):
        daemon = FakeDaemon()

        with fake_ollama(daemon):
            mislabelled = [m for m in studio_label_keys() if not is_cloud_model(m)]

        self.assertEqual(sorted(mislabelled), [])


class ContextWindowContractTests(unittest.TestCase):
    def test_the_srs_bridge_requests_the_same_window_as_the_builder(self):
        from srs_agent.bridge import num_ctx

        daemon = FakeDaemon(models=[cloud_entry("gemma4:31b-cloud")],
                            context_length=8192)

        with fake_ollama(daemon):
            self.assertEqual(num_ctx("gemma4:31b-cloud"),
                             max_context("gemma4:31b-cloud"))
            self.assertEqual(num_ctx("gemma4:31b-cloud"), CLOUD_DEFAULT_CTX)

    def test_no_known_cloud_model_is_ever_given_the_local_window(self):
        daemon = FakeDaemon(context_length=4096)

        with fake_ollama(daemon):
            windows = {m: max_context(m) for m in FALLBACK_CLOUD}

        self.assertTrue(all(w >= CLOUD_DEFAULT_CTX for w in windows.values()),
                        windows)
        self.assertGreater(CLOUD_DEFAULT_CTX, LOCAL_DEFAULT_CTX)


class CloudReadinessFlowTests(unittest.TestCase):
    def test_a_signed_in_daemon_offers_cloud_models_without_an_api_key(self):
        daemon = FakeDaemon(models=[cloud_entry("gemma4:31b-cloud")],
                            account={"name": "someone", "plan": "pro"})

        with fake_ollama(daemon) as client:
            catalog = client.catalog()

        self.assertTrue(catalog["cloud_enabled"])
        self.assertEqual(catalog["cloud_via"], "signed-in")
        self.assertEqual(catalog["cloud_account"], "someone")
        self.assertIn("gemma4:31b-cloud", [e["id"] for e in catalog["cloud"]])

    def test_registering_a_cloud_model_makes_the_catalogue_cloud_ready(self):
        # The whole point of the pull change: an empty signed-in daemon that
        # predates /api/me becomes usable once its first cloud model lands.
        daemon = FakeDaemon(account=None)

        with fake_ollama(daemon) as client:
            self.assertFalse(client.catalog()["cloud_enabled"])

            self.assertTrue(client.pull("gemma4:31b-cloud"))
            after = client.catalog()

        self.assertTrue(after["cloud_enabled"])
        self.assertEqual(after["cloud_via"], "signed-in")
        self.assertIn("gemma4:31b-cloud", after["local"])


if __name__ == "__main__":
    unittest.main()
