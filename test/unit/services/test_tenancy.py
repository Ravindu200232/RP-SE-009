"""One machine, many people: what each request may reach, and who is told about it.

These run against the server's own runtime namespace, the way the handlers see
it. The account store is stood in for, because what is under test is the
routing of a request and of a message, not where the answer is written down.
"""
from __future__ import annotations

import unittest
from unittest import mock

from test import _support                                            # noqa: F401
import server_runtime as server


# Real account ids, because the AWS profile names are made out of them.
ME = {"id": "u1f0e2d3c4b5a697887766554", "username": "ravindu", "admin": False}
THEM = {"id": "u9a8b7c6d5e4f302112233445", "username": "dinuka", "admin": False}
ADMIN = {"id": "u00112233445566778899aabb", "username": "admin", "admin": True}
MINE, THEIRS = ME["id"], THEM["id"]


def owned_by(owners):
    """An account store where `owners` says who owns each ("kind", "key")."""
    def owner_of(kind, key):
        return owners.get((kind, key))

    def owns(user, kind, key):
        if not user or not key:
            return False
        owner = owner_of(kind, key)
        return bool(user.get("admin")) if owner is None else owner == user.get("id")

    return mock.patch.multiple(server.auth_db, owner_of=owner_of, owns=owns)


class MayTests(unittest.TestCase):
    def test_nobody_signed_in_may_do_nothing(self):
        with owned_by({}):
            self.assertFalse(server.may(None, "user"))
            self.assertFalse(server.may(None, "project", "shop"))

    def test_a_project_is_only_its_owners(self):
        with owned_by({("project", "shop"): MINE}):
            self.assertTrue(server.may(ME, "project", "shop"))
            self.assertFalse(server.may(THEM, "project", "shop"))

    def test_a_specification_is_only_its_owners(self):
        with owned_by({("srs", "s1"): MINE}):
            self.assertTrue(server.may(ME, "srs", "s1"))
            self.assertFalse(server.may(THEM, "srs", "s1"))

    def test_a_file_under_a_project_is_the_projects(self):
        path = str(server.PROD_DIR / "shop" / "app" / "page.jsx")
        with owned_by({("project", "shop"): MINE}):
            self.assertTrue(server.may(ME, "project-path", path))
            self.assertFalse(server.may(THEM, "project-path", path))
            self.assertFalse(server.may(ME, "project-path", str(server.PROD_DIR)))

    def test_agentforges_own_settings_are_the_admins(self):
        with owned_by({}):
            self.assertTrue(server.may(ADMIN, "admin"))
            self.assertFalse(server.may(ME, "admin"))

    def test_a_job_belongs_to_whoever_started_it(self):
        with owned_by({}), \
                mock.patch.dict(server._JOBS, {"job_1": {"user": MINE}}, clear=True), \
                mock.patch.dict(server.SRS_JOBS, {"job_2": {"user": MINE}}, clear=True), \
                mock.patch.dict(server.DEPLOY_JOB_OWNERS, {"job_3": MINE}, clear=True):
            for kind, key in (("job", "job_1"), ("srs-job", "job_2"), ("deploy-job", "job_3")):
                self.assertTrue(server.may(ME, kind, key), kind)
                self.assertFalse(server.may(THEM, kind, key), kind)

    def test_a_deployment_belongs_to_whoever_owns_its_project(self):
        with owned_by({("project", "shop"): MINE}), \
                mock.patch.dict(server._RUN_PROJECTS, {"r1": "shop"}, clear=True):
            self.assertTrue(server.may(ME, "deploy-run", "r1"))
            self.assertFalse(server.may(THEM, "deploy-run", "r1"))


class RequestOriginTests(unittest.TestCase):
    def test_a_page_on_another_site_cannot_act_on_this_ones_cookie(self):
        self.assertFalse(server.trusted({"Sec-Fetch-Site": "cross-site",
                                         "Origin": "http://evil.example",
                                         "Host": "127.0.0.1:7824"}))

    def test_the_studios_own_page_is_trusted_through_its_proxy(self):
        self.assertTrue(server.trusted({"Sec-Fetch-Site": "same-origin",
                                        "Origin": "https://studio.example",
                                        "X-Forwarded-Host": "studio.example",
                                        "Host": "127.0.0.1:7824"}))

    def test_a_generated_app_on_its_own_preview_host_is_not_the_studio(self):
        self.assertFalse(server.trusted({"Sec-Fetch-Site": "same-site",
                                         "Origin": "http://p-abc.localhost:7824",
                                         "Host": "127.0.0.1:7824"}))

    def test_something_that_is_not_a_browser_carries_no_cookie_to_ride_on(self):
        self.assertTrue(server.trusted({"Host": "127.0.0.1:7824"}))

    def test_the_first_forwarded_address_is_the_one_the_browser_used(self):
        self.assertEqual(server.studio_host({"X-Forwarded-Host": "studio.example, inner",
                                             "Host": "127.0.0.1:7824"}), "studio.example")


class SessionCookieTests(unittest.TestCase):
    def test_the_cookie_is_out_of_reach_of_a_page_and_of_other_sites(self):
        cookie = server.session_cookie("t0ken", secure=True)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertIn("Secure", cookie)

    def test_signing_out_removes_it(self):
        self.assertIn("Max-Age=0", server.session_cookie("", secure=False))


class MessageDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.mine, self.theirs, self.admin = object(), object(), object()
        sockets = {self.mine: ME, self.theirs: THEM, self.admin: ADMIN}
        self.everyone = mock.patch.dict(server.WS_USERS, sockets, clear=True)
        self.everyone.start()
        self.addCleanup(self.everyone.stop)
        server.clients.update(sockets)
        self.addCleanup(lambda: [server.clients.discard(s) for s in sockets])
        server.act_as(None)
        self.addCleanup(server.act_as, None)

    def test_a_build_is_reported_only_to_whoever_owns_the_project(self):
        with owned_by({("project", "shop"): MINE}):
            self.assertEqual(server.recipients({"type": "log", "project": "shop"}),
                             [self.mine])

    def test_a_message_about_no_project_goes_to_whoever_it_is_for(self):
        with owned_by({}):
            server.act_as(THEM)
            self.assertEqual(server.recipients({"type": "log"}), [self.theirs])

    def test_the_server_talking_about_itself_is_for_everyone(self):
        with owned_by({}):
            self.assertEqual(len(server.recipients({"type": "log"})), 3)


class SettingsViewTests(unittest.TestCase):
    def setUp(self):
        server.act_as(None)
        self.addCleanup(server.act_as, None)

    def view(self, user, saved=None):
        server.act_as(user)
        with mock.patch.object(server.auth_db, "user_settings", return_value=saved or {}):
            return server.shared_settings({"ollama_host": "http://localhost:11434",
                                           "api_key_hint": "…1234",
                                           "mongodb_uri_hint": "mongodb://…/db",
                                           "mongodb_uri_set": True})

    def test_agentforges_own_key_and_database_are_not_shown_to_everyone(self):
        answer = self.view(ME)
        self.assertEqual(answer["api_key_hint"], "")
        self.assertFalse(answer["mongodb_uri_set"])
        self.assertFalse(answer["admin"])

    def test_the_admin_still_sees_them(self):
        answer = self.view(ADMIN)
        self.assertEqual(answer["api_key_hint"], "…1234")
        self.assertTrue(answer["admin"])

    def test_each_person_sees_their_own_deployment_accounts(self):
        answer = self.view(ME, {"github_token": "gh", "github_login": "ravindu",
                                "vercel_token": "abcd1234", "aws_profile": "af-u1-console"})
        self.assertEqual(answer["deploy"]["github_login"], "ravindu")
        self.assertTrue(answer["deploy"]["github_token_set"])
        self.assertEqual(answer["deploy"]["vercel_token_hint"], "…1234")
        self.assertNotIn("gh", str(answer["deploy"].values()))


class DeploymentRequestTests(unittest.TestCase):
    def rewrite(self, method, path, body, saved=None):
        with mock.patch.object(server.auth_db, "user_settings", return_value=saved or {}):
            return server.deploy_request_for(ME, method, path, body)

    def test_an_aws_profile_is_named_for_the_person_asking(self):
        self.assertTrue(server.aws_profile_for(ME, "console").startswith(server._profile_prefix(ME)))
        mine = server.aws_profile_for(ME, "console")
        self.assertEqual(server.aws_profile_for(ME, mine), mine)
        self.assertNotEqual(server.aws_profile_for(THEM, "console"), mine)

    def test_nobody_can_deploy_with_someone_elses_aws_profile(self):
        _, body, _ = self.rewrite("POST", "/api/runs/r1/deploy",
                                  {"approved": True, "aws_profile": server.aws_profile_for(THEM, "console")})
        self.assertTrue(body["aws_profile"].startswith(server._profile_prefix(ME)))
        self.assertNotIn(server.aws_profile_for(THEM, "console"), body["aws_profile"])

    def test_an_empty_profile_does_not_fall_back_to_this_machines_account(self):
        _, body, _ = self.rewrite("POST", "/api/aws/preflight", {"region": "ap-south-1"})
        self.assertTrue(body["aws_profile"].startswith(server._profile_prefix(ME)))

    def test_stored_credentials_are_never_taken_from_a_request(self):
        _, body, _ = self.rewrite("POST", "/api/aws/preflight",
                                  {"credential_reference": "someone-elses"})
        self.assertNotIn("credential_reference", body)

    def test_a_run_is_started_in_the_name_of_whoever_asked(self):
        _, body, _ = self.rewrite("POST", "/api/runs/r1/deploy",
                                  {"approved": True, "owner": THEIRS})
        self.assertEqual(body["owner"], MINE)

    def test_signing_this_machine_in_is_refused(self):
        for tool in ("github", "vercel", "ollama"):
            with self.assertRaises(ValueError, msg=tool):
                self.rewrite("POST", "/api/onboarding/login", {"tool": tool})

    def test_an_aws_browser_sign_in_is_allowed_under_their_own_profile(self):
        _, body, _ = self.rewrite("POST", "/api/onboarding/login",
                                  {"tool": "aws-console-login", "profile": "agentforge-console"})
        self.assertTrue(body["profile"].startswith(server._profile_prefix(ME)))

    def test_a_vercel_check_uses_their_own_saved_token(self):
        _, body, answer = self.rewrite("POST", "/api/aws/vercel/status", {"token": ""},
                                       saved={"vercel_token": "vc-mine"})
        self.assertEqual(body["token"], "vc-mine")
        self.assertIsNone(answer)
        _, _, nothing = self.rewrite("POST", "/api/aws/vercel/status", {"token": ""})
        self.assertFalse(nothing["connected"])


class DeploymentViewTests(unittest.TestCase):
    def test_a_list_of_deployments_shows_only_their_own(self):
        runs = {"runs": [{"id": "r1", "project_path": str(server.PROD_DIR / "shop")},
                         {"id": "r2", "project_path": str(server.PROD_DIR / "blog")}]}
        with owned_by({("project", "shop"): MINE, ("project", "blog"): THEIRS}):
            self.assertEqual([run["id"] for run in server.visible_runs(ME, runs)["runs"]], ["r1"])

    def test_the_accounts_view_shows_their_own_sign_ins(self):
        ours, theirs = (server.aws_profile_for(ME, "console"),
                        server.aws_profile_for(THEM, "console"))
        status = {"aws_profiles": [ours, theirs, "default"],
                  "aws_identities": {theirs: {"account": "2"}},
                  "github_authenticated": True, "github_account": "the-machine"}
        with mock.patch.object(server.auth_db, "user_settings",
                               return_value={"github_token": "", "github_login": ""}):
            mine = server.visible_onboarding(ME, status)
        self.assertEqual(mine["aws_profiles"], [ours])
        self.assertEqual(mine["aws_identities"], {})
        self.assertFalse(mine["github_authenticated"])
        self.assertEqual(mine["github_account"], "")


class SpecificationViewTests(unittest.TestCase):
    def test_the_list_is_cut_down_to_their_own(self):
        answer = {"projects": [{"id": "s1"}, {"id": "s2"}]}
        with owned_by({("srs", "s1"): MINE, ("srs", "s2"): THEIRS}):
            self.assertEqual(server.visible_srs_list(answer, ME), {"projects": [{"id": "s1"}]})

    def test_a_finished_job_makes_the_new_specification_its_starters(self):
        claimed = []
        server.SRS_JOBS["job_9"] = {"user": MINE, "create": True, "listing": False}
        self.addCleanup(server.SRS_JOBS.pop, "job_9", None)
        done = {"status": "done", "result": {"project": {"id": "s9"}}}
        with mock.patch.object(server.auth_db, "claim",
                               side_effect=lambda *a: claimed.append(a)):
            server.srs_job_answered("job_9", done, ME)
        self.assertEqual(claimed, [("srs", "s9", MINE)])

    def test_a_listing_job_is_answered_with_their_own(self):
        server.SRS_JOBS["job_8"] = {"user": MINE, "create": False, "listing": True}
        self.addCleanup(server.SRS_JOBS.pop, "job_8", None)
        done = {"status": "done", "result": {"projects": [{"id": "s1"}, {"id": "s2"}]}}
        with owned_by({("srs", "s1"): MINE, ("srs", "s2"): THEIRS}):
            answer = server.srs_job_answered("job_8", done, ME)
        self.assertEqual(answer["result"]["projects"], [{"id": "s1"}])


if __name__ == "__main__":
    unittest.main()
