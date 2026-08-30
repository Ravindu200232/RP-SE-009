from __future__ import annotations

import unittest

from test import _support
from test._support import FakeDaemon, cloud_entry, fake_ollama, local_entry
from agents.core.llm.llm_client import (CLOUD_DEFAULT_CTX, FALLBACK_CLOUD,
                                       LOCAL_DEFAULT_CTX, is_cloud_model,
                                       max_context)


class CloudModelRoutingTests(unittest.TestCase):
    def test_a_cloud_suffix_is_recognized_without_asking_the_daemon(self):
        daemon = FakeDaemon()

        with fake_ollama(daemon):
            self.assertTrue(is_cloud_model("gemma4:31b-cloud"))
            self.assertTrue(is_cloud_model("glm-4.6:cloud"))

        self.assertEqual(daemon.hit("tags"), 0)

    def test_a_known_cloud_model_is_cloud_before_it_has_been_pulled(self):
        # `bjoernb/gemma4-31b-fast:latest` proxies to ollama.com but carries no
        # -cloud suffix, so the name test alone called it local and would have
        # handed it the small local window on its very first use.
        daemon = FakeDaemon()

        with fake_ollama(daemon):
            self.assertTrue(is_cloud_model("bjoernb/gemma4-31b-fast:latest"))

    def test_a_known_cloud_model_resolves_with_or_without_its_latest_tag(self):
        daemon = FakeDaemon()

        with fake_ollama(daemon):
            self.assertTrue(is_cloud_model("bjoernb/gemma4-31b-fast"))
            self.assertTrue(is_cloud_model("bjoernb/gemma4-31b-fast:latest"))

    def test_a_proxied_model_is_cloud_even_with_an_ordinary_name(self):
        daemon = FakeDaemon(models=[cloud_entry("someone/wrapper:latest")])

        with fake_ollama(daemon):
            self.assertTrue(is_cloud_model("someone/wrapper:latest"))

    def test_an_installed_local_model_is_not_treated_as_cloud(self):
        daemon = FakeDaemon(models=[local_entry("llama3.1:8b")])

        with fake_ollama(daemon):
            self.assertFalse(is_cloud_model("llama3.1:8b"))
            self.assertFalse(is_cloud_model(""))


class CloudContextTests(unittest.TestCase):
    def test_cloud_context_is_never_capped_below_the_published_default(self):
        # A cloud model proxied by the local daemon can report a stub window.
        daemon = FakeDaemon(models=[cloud_entry("gemma4:31b-cloud")],
                            context_length=8192)

        with fake_ollama(daemon):
            self.assertEqual(max_context("gemma4:31b-cloud"), CLOUD_DEFAULT_CTX)

    def test_cloud_context_keeps_a_window_larger_than_the_default(self):
        daemon = FakeDaemon(models=[cloud_entry("kimi-k2:1t-cloud")],
                            context_length=CLOUD_DEFAULT_CTX * 4)

        with fake_ollama(daemon):
            self.assertEqual(max_context("kimi-k2:1t-cloud"),
                             CLOUD_DEFAULT_CTX * 4)

    def test_a_cloud_model_reporting_no_window_still_gets_the_default(self):
        daemon = FakeDaemon(models=[cloud_entry("glm-4.6:cloud")],
                            context_length=None)

        with fake_ollama(daemon):
            self.assertEqual(max_context("glm-4.6:cloud"), CLOUD_DEFAULT_CTX)

    def test_a_local_model_is_never_asked_for_more_than_it_supports(self):
        daemon = FakeDaemon(models=[local_entry("llama3.1:8b")],
                            context_length=8192)

        with fake_ollama(daemon):
            self.assertEqual(max_context("llama3.1:8b"), 8192)

    def test_a_local_model_stays_on_the_conservative_default(self):
        daemon = FakeDaemon(models=[local_entry("llama3.1:70b")],
                            context_length=CLOUD_DEFAULT_CTX)

        with fake_ollama(daemon):
            self.assertEqual(max_context("llama3.1:70b"), LOCAL_DEFAULT_CTX)


class CloudPullTests(unittest.TestCase):
    def test_pulling_a_cloud_model_registers_it_with_the_daemon(self):
        # Cloud models used to return success without any request at all, so a
        # signed-in daemon was never asked to proxy them.
        daemon = FakeDaemon()

        with fake_ollama(daemon) as client:
            self.assertTrue(client.pull("gemma4:31b-cloud"))

        self.assertEqual(daemon.hit("pull"), 1)

    def test_a_registered_cloud_model_becomes_visible_immediately(self):
        daemon = FakeDaemon()

        with fake_ollama(daemon) as client:
            self.assertEqual(client.list_local(), [])
            client.pull("gemma4:31b-cloud")

            # The pull has to drop the tag cache, or every later answer is
            # served from the listing taken before the model existed.
            self.assertIn("gemma4:31b-cloud", client.list_local())
            self.assertTrue(client.signed_in())

    def test_a_refused_pull_is_reported_as_a_failure(self):
        daemon = FakeDaemon(pull_error="pull model manifest: file does not exist")

        with fake_ollama(daemon) as client:
            with self.assertLogs("ollama", level="ERROR") as captured:
                self.assertFalse(client.pull("bjoernb/does-not-exist:cloud"))

        self.assertIn("file does not exist", captured.output[0])

    def test_a_cloud_pull_succeeds_on_an_api_key_when_the_daemon_is_absent(self):
        daemon = FakeDaemon(reachable=False)

        with fake_ollama(daemon, api_key="sk-test") as client:
            self.assertTrue(client.pull("gemma4:31b-cloud"))

    def test_a_local_pull_still_fails_when_the_daemon_is_absent(self):
        daemon = FakeDaemon(reachable=False)

        with fake_ollama(daemon, api_key="sk-test") as client:
            with self.assertLogs("ollama", level="ERROR"):
                self.assertFalse(client.pull("llama3.1:8b"))


class SigninDetectionTests(unittest.TestCase):
    def test_a_signed_in_daemon_with_nothing_pulled_is_still_signed_in(self):
        # The reported bug: signed in as a real account, zero models pulled,
        # and the studio told the user to sign in.
        daemon = FakeDaemon(account={"name": "someone", "email": "a@b.c",
                                     "plan": "pro"})

        with fake_ollama(daemon) as client:
            self.assertEqual(client.list_local(), [])
            self.assertTrue(client.signed_in())
            self.assertTrue(client.cloud_ready())
            self.assertEqual(client.account()["name"], "someone")

    def test_a_daemon_that_is_not_signed_in_reports_no_account(self):
        daemon = FakeDaemon(account=None)

        with fake_ollama(daemon) as client:
            self.assertEqual(client.account(), {})
            self.assertFalse(client.signed_in())
            self.assertFalse(client.cloud_ready())

    def test_an_older_daemon_is_still_detected_by_its_proxied_models(self):
        # `/api/me` predates neither every build nor every fork, so the older
        # remote_host signal has to keep working on its own.
        daemon = FakeDaemon(models=[cloud_entry("gpt-oss:120b-cloud")],
                            account=None)

        with fake_ollama(daemon) as client:
            self.assertEqual(client.account(), {})
            self.assertTrue(client.signed_in())

    def test_readiness_tells_an_empty_daemon_from_an_absent_one(self):
        running = FakeDaemon()
        with fake_ollama(running) as client:
            self.assertEqual(client.list_local(), [])
            self.assertTrue(client.daemon_ready())

        stopped = FakeDaemon(reachable=False)
        with fake_ollama(stopped) as client:
            self.assertEqual(client.list_local(), [])
            self.assertFalse(client.daemon_ready())

    def test_an_api_key_reaches_cloud_models_without_any_daemon(self):
        daemon = FakeDaemon(reachable=False)

        with fake_ollama(daemon, api_key="sk-test") as client:
            self.assertFalse(client.daemon_ready())
            self.assertTrue(client.cloud_ready())
            self.assertTrue(client.has_model("gemma4:31b-cloud"))


class CatalogueShapeTests(unittest.TestCase):
    def test_the_catalogue_falls_back_to_known_cloud_models_when_empty(self):
        daemon = FakeDaemon()

        with fake_ollama(daemon) as client:
            catalog = client.catalog()

        offered = [entry["id"] for entry in catalog["cloud"]]
        self.assertEqual(offered, list(FALLBACK_CLOUD))
        self.assertTrue(all(not entry["installed"] for entry in catalog["cloud"]))

    def test_every_offered_cloud_entry_carries_the_window_it_will_request(self):
        daemon = FakeDaemon(models=[cloud_entry("gemma4:31b-cloud")],
                            context_length=8192)

        with fake_ollama(daemon) as client:
            catalog = client.catalog()

        entry = next(e for e in catalog["cloud"] if e["id"] == "gemma4:31b-cloud")
        self.assertEqual(entry["ctx"], CLOUD_DEFAULT_CTX)
        self.assertEqual(entry["tag"], "cloud")
        self.assertIn(f"{CLOUD_DEFAULT_CTX // 1024}k", entry["desc"])


if __name__ == "__main__":
    unittest.main()
