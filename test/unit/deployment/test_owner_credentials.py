"""A deployment signs in with its owner's accounts, never with this machine's.

The agent was written for one person at one desk: it used the `gh` login and
the Vercel CLI's token that were on the machine. Run inside a shared
AgentForge, that would put everyone's deployments in the machine owner's
accounts — so AgentForge registers a provider, every run names its owner, and
with a provider registered the machine's own logins are not a fallback at all.
"""
from __future__ import annotations

import sys
import threading
import unittest
from types import SimpleNamespace
from unittest import mock

from test import _support

_AGENT = str(_support.ROOT / "deployment-agent" / "deploy_agent")
if _AGENT not in sys.path:
    sys.path.insert(0, _AGENT)

from deployment_agent import owner_credentials, tools, vercel_auth      # noqa: E402


ACCOUNTS = {
    "u1": {"github_token": "gh-one", "vercel_token": "vc-one"},
    "u2": {"github_token": "gh-two", "vercel_token": ""},
}


class OwnerCredentialsTestCase(unittest.TestCase):
    def setUp(self):
        self.addCleanup(owner_credentials.register, None)
        self.addCleanup(owner_credentials.set_owner, "")
        owner_credentials.set_owner("")

    def serving(self):
        owner_credentials.register(lambda owner: dict(ACCOUNTS.get(owner) or {}))


class WhoseAccountsTests(OwnerCredentialsTestCase):
    def test_on_its_own_the_agent_carries_nothing_extra(self):
        self.assertFalse(owner_credentials.active())
        self.assertEqual(owner_credentials.command_env(), {})

    def test_a_run_carries_its_own_owners_token(self):
        self.serving()
        with owner_credentials.acting_for("u1"):
            self.assertEqual(owner_credentials.command_env()["GH_TOKEN"], "gh-one")
        with owner_credentials.acting_for("u2"):
            self.assertEqual(owner_credentials.command_env()["GH_TOKEN"], "gh-two")

    def test_without_a_token_gh_is_still_kept_away_from_this_machines_login(self):
        self.serving()
        with owner_credentials.acting_for("nobody"):
            environment = owner_credentials.command_env()
        self.assertNotIn("GH_TOKEN", environment)
        self.assertTrue(environment["GH_CONFIG_DIR"])

    def test_two_runs_at_once_do_not_borrow_each_others_accounts(self):
        self.serving()
        seen = {}

        def record(owner):
            with owner_credentials.acting_for(owner):
                barrier.wait(timeout=5)
                seen[owner] = owner_credentials.command_env().get("GH_TOKEN")

        barrier = threading.Barrier(2)
        threads = [threading.Thread(target=record, args=(owner,)) for owner in ("u1", "u2")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        self.assertEqual(seen, {"u1": "gh-one", "u2": "gh-two"})

    def test_work_handed_to_another_thread_keeps_its_owner(self):
        self.serving()
        seen = []
        with owner_credentials.acting_for("u1"):
            work = owner_credentials.carry(lambda: seen.append(owner_credentials.owner()))
        thread = threading.Thread(target=work)
        thread.start()
        thread.join(timeout=5)
        self.assertEqual(seen, ["u1"])


class CommandTests(OwnerCredentialsTestCase):
    def test_a_command_run_for_someone_signs_in_as_them(self):
        self.serving()
        done = SimpleNamespace(stdout="", stderr="", returncode=0)
        with mock.patch.object(tools.subprocess, "run", return_value=done) as run, \
                mock.patch.object(tools, "resolve_command", side_effect=lambda name: name), \
                owner_credentials.acting_for("u1"):
            tools.run_command(["gh", "repo", "list"])
        environment = run.call_args.kwargs["env"]
        self.assertEqual(environment["GH_TOKEN"], "gh-one")
        self.assertEqual(environment["GITHUB_TOKEN"], "gh-one")


class VercelTokenTests(OwnerCredentialsTestCase):
    def test_the_machines_vercel_login_is_used_when_nobody_else_is_deploying(self):
        with mock.patch.object(vercel_auth, "read_vercel_token", return_value="machine"):
            self.assertEqual(vercel_auth.require_vercel_token(), "machine")

    def test_deploying_for_someone_it_is_their_token_or_none_at_all(self):
        self.serving()
        with mock.patch.object(vercel_auth, "read_vercel_token", return_value="machine"):
            with owner_credentials.acting_for("u1"):
                self.assertEqual(vercel_auth.require_vercel_token(), "vc-one")
            with owner_credentials.acting_for("u2"):
                with self.assertRaises(ValueError):
                    vercel_auth.require_vercel_token()

    def test_a_token_handed_in_for_the_run_wins(self):
        self.serving()
        with owner_credentials.acting_for("u1"):
            self.assertEqual(vercel_auth.require_vercel_token("for-this-run"), "for-this-run")


if __name__ == "__main__":
    unittest.main()
