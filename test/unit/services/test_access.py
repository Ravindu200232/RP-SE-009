"""What each API route needs before a shared AgentForge answers it.

The table is read off the path and the body, before a handler runs, so these
are the checks that decide whether one person's request can reach another
person's project, specification or deployment. The last test is the important
one: a route nobody has classified is the admin's, so a route added later is
closed until someone decides who it is for.
"""
from __future__ import annotations

import unittest

from test import _support                                            # noqa: F401
from server_modules.services.access import rule


class AgentForgeRouteTests(unittest.TestCase):
    def test_a_signed_in_person_may_read_their_own_lists(self):
        for path in ("/projects", "/models", "/settings", "/srs-status",
                     "/deploy-status", "/image-check", "/mongo"):
            self.assertEqual(rule("GET", path), ("user", ""), path)

    def test_a_path_that_names_a_project_needs_that_project(self):
        self.assertEqual(rule("GET", "/files/shop"), ("project", "shop"))
        self.assertEqual(rule("GET", "/prototype/shop/index.html"), ("project", "shop"))
        self.assertEqual(rule("GET", "/qa-screenshot/shop"), ("project", "shop"))
        self.assertEqual(rule("GET", "/runtime/shop"), ("project", "shop"))
        self.assertEqual(rule("GET", "/deploy-results/shop"), ("project", "shop"))
        self.assertEqual(rule("POST", "/open/shop"), ("project", "shop"))
        self.assertEqual(rule("POST", "/runtime/shop/activity"), ("project", "shop"))

    def test_a_body_that_names_a_project_needs_that_project(self):
        for path in ("/delete-project", "/save-file", "/element-edit", "/feature",
                     "/agent-update", "/undo", "/shot", "/deploy-start", "/resume"):
            self.assertEqual(rule("POST", path, {"project": "shop"}),
                             ("project", "shop"), path)

    def test_an_upload_without_a_project_is_nobodys_in_particular(self):
        self.assertEqual(rule("POST", "/image", {}), ("user", ""))
        self.assertEqual(rule("POST", "/image", {"project": "shop"}), ("project", "shop"))

    def test_building_from_a_specification_needs_that_specification(self):
        self.assertEqual(rule("POST", "/agent-build", {"srs_id": "s1"}), ("srs", "s1"))
        self.assertEqual(rule("POST", "/agent-build", {}), ("user", ""))
        self.assertEqual(rule("POST", "/keep-srs", {"srs_id": "s1"}), ("srs", "s1"))
        self.assertEqual(rule("POST", "/discard-srs", {"srs_id": "s1"}), ("srs", "s1"))

    def test_a_job_belongs_to_whoever_started_it(self):
        self.assertEqual(rule("GET", "/jobs/job_1"), ("job", "job_1"))

    def test_the_run_in_progress_is_one_persons(self):
        self.assertEqual(rule("GET", "/decisions"), ("run", ""))
        self.assertEqual(rule("POST", "/decision", {"id": "1"}), ("run", ""))

    def test_a_route_nobody_classified_is_the_admins(self):
        self.assertEqual(rule("GET", "/something-new"), ("admin", ""))
        self.assertEqual(rule("POST", "/something-new", {"project": "shop"}), ("admin", ""))
        self.assertEqual(rule("POST", "/image-start"), ("admin", ""))


class SpecificationRouteTests(unittest.TestCase):
    def test_making_one_is_open_and_reading_one_is_not(self):
        create = {"method": "POST", "path": "/projects", "body": {"idea": "a shop"}}
        self.assertEqual(rule("POST", "/srs/jobs", create), ("srs-create", ""))
        answer = {"method": "POST", "path": "/projects/s1/interview/answer"}
        self.assertEqual(rule("POST", "/srs/jobs", answer), ("srs", "s1"))

    def test_the_list_is_open_and_answered_with_their_own(self):
        self.assertEqual(rule("GET", "/srs/projects"), ("user", ""))
        listing = {"method": "GET", "path": "/projects"}
        self.assertEqual(rule("POST", "/srs/jobs", listing), ("user", ""))

    def test_reading_one_needs_that_specification(self):
        self.assertEqual(rule("GET", "/srs/projects/s1/srs-json"), ("srs", "s1"))
        self.assertEqual(rule("GET", "/srs/projects/s1/events/stream"), ("srs", "s1"))
        self.assertEqual(rule("GET", "/srs/jobs/job_2"), ("srs-job", "job_2"))


class DeploymentRouteTests(unittest.TestCase):
    def test_a_run_belongs_to_whoever_owns_its_project(self):
        self.assertEqual(rule("GET", "/deploy/runs/r1"), ("deploy-run", "r1"))
        self.assertEqual(rule("GET", "/deploy/runs/r1/monitor"), ("deploy-run", "r1"))
        self.assertEqual(rule("POST", "/deploy/runs/r1/deploy", {"approved": True}),
                         ("deploy-run", "r1"))

    def test_analysis_needs_the_project_at_that_path(self):
        self.assertEqual(rule("POST", "/deploy/runs/analyze", {"path": "D:/p/shop"}),
                         ("project-path", "D:/p/shop"))

    def test_accounts_and_lists_are_each_persons_own(self):
        for path in ("/deploy/runs", "/deploy/onboarding/status", "/deploy/aws/sso/start",
                     "/deploy/mongodb/check", "/deploy/health"):
            self.assertEqual(rule("GET", path)[0], "user", path)

    def test_a_job_carries_the_rule_of_what_it_runs(self):
        wrapped = {"method": "POST", "path": "/runs/r1/teardown", "body": {"confirm": True}}
        self.assertEqual(rule("POST", "/deploy/jobs", wrapped), ("deploy-run", "r1"))
        self.assertEqual(rule("GET", "/deploy/jobs/job_3"), ("deploy-job", "job_3"))


if __name__ == "__main__":
    unittest.main()
