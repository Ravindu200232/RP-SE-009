"""The providers a person keeps once, and what must never leak out of them.

A plugin's credentials are the most dangerous thing this application stores:
they are somebody's real Stripe secret and somebody's real Supabase key. So
what is tested here is mostly the negative - that a value never comes back to
a browser, never reaches a log line, and never appears in the project except
in the one file the agent's own tools refuse to open.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from test import _support  # noqa: F401
from server_modules.builder import plugins

ROOT = Path(__file__).resolve().parents[3]


class CatalogTests(unittest.TestCase):
    """The catalogue is read from the skills, never restated beside them."""

    def setUp(self):
        self.rows = plugins.catalog()
        self.by_id = {row["id"]: row for row in self.rows}

    def test_every_plugin_names_a_skill_that_ships(self):
        for row in self.rows:
            with self.subTest(row["id"]):
                self.assertTrue((plugins.SKILL_ROOT / row["skill"] / "SKILL.md").is_file(),
                                f"{row['id']} points at a skill with no page to read")

    def test_every_mode_asks_for_something_and_shows_an_example(self):
        """Told only "API key", people paste an account id."""
        for row in self.rows:
            for mode in row["modes"]:
                with self.subTest(f"{row['id']}/{mode['choice']}"):
                    self.assertTrue(mode["fields"])
                    for field in mode["fields"]:
                        self.assertTrue(field["example"],
                                        f"{field['key']} has no example value")

    def test_a_field_is_the_environment_variable_it_will_become(self):
        for row in self.rows:
            for mode in row["modes"]:
                for field in mode["fields"]:
                    with self.subTest(field["key"]):
                        self.assertRegex(field["key"], plugins.ENV_NAME)

    def test_modes_of_one_plugin_are_what_share_its_settings(self):
        """Stripe test and Stripe live write the same three keys.

        Which is the whole reason they are one card with a switch rather than
        two cards: as two plugins they would overwrite each other's values and
        the person would have no way to tell which was in the project.
        """
        stripe = self.by_id["stripe"]
        self.assertEqual(len(stripe["modes"]), 2)
        first, second = ({f["key"] for f in mode["fields"]} for mode in stripe["modes"])
        self.assertEqual(first, second)

    def test_every_group_a_plugin_claims_is_a_group_that_exists(self):
        declared = set(plugins.groups())
        self.assertTrue(declared)
        for row in self.rows:
            with self.subTest(row["id"]):
                self.assertIn(row["group"], declared)

    def test_an_icon_is_named_and_present(self):
        for row in self.rows:
            with self.subTest(row["id"]):
                self.assertTrue(row["icon"])
                self.assertTrue((ROOT / "studio" / "public" / "plugins" / row["icon"]).is_file(),
                                f"{row['id']} names an icon that is not there")

    def test_a_sign_in_is_only_claimed_where_one_is_wired(self):
        """A declared capability that does nothing is worse than none."""
        from server_modules.deploy.cli_signin import PROVIDERS
        for row in self.rows:
            if row["signin"]:
                with self.subTest(row["id"]):
                    self.assertIn(row["signin"], PROVIDERS)


class ProjectOptInTests(unittest.TestCase):
    """Ticking one for an app, which is the whole opt-in."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def test_nothing_is_on_until_something_is_ticked(self):
        self.assertEqual(plugins.enabled_for(self.root), [])
        self.assertEqual(plugins.skills_for(self.root), [])

    def test_ticking_records_the_plugins_and_the_skills_they_entitle(self):
        """Both, because the two readers cannot see each other.

        The server reads `enabled` to know whose credentials to merge in; the
        builder-agent reads `skills` to know which pages the model may read,
        and it cannot import this module to work that out for itself.
        """
        plugins.set_enabled(self.root, ["supabase", "google"])
        body = json.loads((self.root / plugins.PROJECT_FILE).read_text(encoding="utf-8"))
        self.assertEqual(body["enabled"], ["supabase", "google"])
        self.assertEqual(body["skills"], ["image-uploads", "social-signin"])

    def test_the_agent_reads_the_same_file_this_wrote(self):
        sys.path.insert(0, str(ROOT / "builder-agent"))
        from builder_agent.loop import _plugin_skills
        plugins.set_enabled(self.root, ["stripe"])
        self.assertEqual(_plugin_skills(self.root), ["payments"])

    def test_a_name_nobody_ships_is_refused_rather_than_recorded(self):
        self.assertEqual(plugins.set_enabled(self.root, ["stripe", "not-a-plugin"]),
                         ["stripe"])

    def test_unticking_everything_leaves_nothing_behind(self):
        plugins.set_enabled(self.root, ["stripe"])
        self.assertEqual(plugins.set_enabled(self.root, []), [])
        self.assertEqual(plugins.skills_for(self.root), [])

    def test_a_ticked_plugin_forces_its_skill_in_whatever_the_request_says(self):
        """Somebody who turned Stripe on has said the app takes money."""
        sys.path.insert(0, str(ROOT / "builder-agent"))
        from builder_agent.skills import read_manifest, select
        entries = read_manifest()
        self.assertNotIn("payments", select(entries, "", "a simple todo list", "nextjs-mongo"))
        self.assertIn("payments", select(entries, "", "a simple todo list", "nextjs-mongo",
                                         forced=["payments"]))
        # Even a request that rules the word out: the tick is the later, and
        # more explicit, statement of intent.
        self.assertIn("payments", select(entries, "", "a shop with payment nathuwa",
                                         "nextjs-mongo", forced=["payments"]))

    def test_no_credential_is_returned_for_a_project_nobody_owns(self):
        plugins.set_enabled(self.root, ["stripe"])
        self.assertEqual(plugins.env_for("", self.root), {})


if __name__ == "__main__":
    unittest.main()
