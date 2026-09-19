"""Who a step belongs to, and what a public page actually shows.

Both rules here are string matches over plan prose, and both were quietly wrong
in a way no schema check could catch: the resulting requirements were
well-formed, traceable and false. They were found by generating a real SRS for a
multi-clinic healthcare platform, where the reviewer flagged two requirements it
could not fix - because neither was written by the model. They come from this
deterministic projection, so the fix has to be here.

  * `The system shall let visitors view patients.` A sign-up page is open to
    anyone and its copy read "Create the approved Patient account.", which named
    the patients table. An auth page describes the account it creates, never a
    table it lists.
  * `The system shall let approved users create one doctor record.` with
    `allowed_roles: ["patient"]`. The step "Doctor uses Clinical Workspace to
    record consultation" sits inside the patient's visit journey, and the
    journey's owner was credited with every step in it.
"""
import unittest

from test import _support  # noqa: F401 - puts the agent packages on the path
from srs_agent.app.knowledge.plan_srs_access import (
    _plan_role_names, _public_reads_table, _role_actions_for_table, _step_actor,
)


PLAN = {
    "users": [
        {"role": "Patient", "can_do": ["Search for doctors by specialty and clinic"]},
        {"role": "Doctor", "can_do": ["Record consultation notes and diagnosis"]},
        {"role": "Nurse", "can_do": ["View patient schedules"]},
        {"role": "Lab Technician", "can_do": ["Upload result files"]},
        {"role": "Clinic Manager", "can_do": ["Approve refunds above LKR 10,000"]},
        {"role": "System Administrator", "can_do": ["Review audit logs"]},
    ],
    "workflows": [
        {"name": "Patient Visit Journey", "who": "Patient", "steps": [
            "Patient uses Doctor Search to find a provider",
            "Doctor uses Clinical Workspace to record consultation and order LabTest",
            "Lab Technician uploads results to Lab Queue and marks as released",
        ]},
        {"name": "Handling High-Value Refund", "who": "Receptionist", "steps": [
            "Receptionist initiates refund request in Front Desk",
            "Clinic Manager reviews the request in Refund Approval screen",
            "Manager approves refund, triggering the payment provider",
        ]},
        {"name": "What the doctor does here", "who": "Doctor", "steps": [
            "Manage weekly availability",
            "View daily schedule",
        ]},
    ],
}

ROLES = _plan_role_names(PLAN)


class StepActor(unittest.TestCase):
    def test_a_step_belongs_to_the_role_it_names(self):
        """The defect: this step granted patients the right to create doctors."""
        self.assertEqual(
            _step_actor("Doctor uses Clinical Workspace to record consultation",
                        ROLES, "Patient"),
            "Doctor")

    def test_a_two_word_role_is_matched_whole(self):
        self.assertEqual(
            _step_actor("Lab Technician uploads results to Lab Queue", ROLES, "Patient"),
            "Lab Technician")

    def test_a_shortened_role_matches_its_last_word(self):
        """Plans write "Manager approves refund" for the Clinic Manager."""
        self.assertEqual(
            _step_actor("Manager approves refund", ROLES, "Receptionist"),
            "Clinic Manager")

    def test_a_role_named_later_is_the_object_not_the_actor(self):
        """"View patient schedules" is the nurse's duty, not the patient's."""
        self.assertEqual(_step_actor("View patient schedules", ROLES, "Nurse"), "Nurse")

    def test_a_verb_that_looks_like_a_role_is_not_one(self):
        """Manage / Manager. Exact words only, or every plan grows a manager."""
        self.assertEqual(_step_actor("Manage weekly availability", ROLES, "Doctor"), "Doctor")

    def test_a_step_with_no_role_keeps_the_workflow_owner(self):
        self.assertEqual(_step_actor("View daily schedule", ROLES, "Doctor"), "Doctor")

    def test_longer_role_names_win(self):
        """"Clinic Manager" must not be read as some other Manager."""
        self.assertEqual(
            _step_actor("Clinic Manager reviews the request", ROLES, "Receptionist"),
            "Clinic Manager")


class TableActions(unittest.TestCase):
    def test_the_doctor_creates_doctor_records_not_the_patient(self):
        actions = _role_actions_for_table(PLAN, "doctors")
        self.assertEqual(actions["create"], ["doctor"])
        self.assertNotIn("patient", actions["create"])

    def test_the_patient_still_reads_doctors(self):
        """The fix must not cost the patient the search they were promised."""
        self.assertIn("patient", _role_actions_for_table(PLAN, "doctors")["read"])


class PublicReads(unittest.TestCase):
    AUTH = [
        {"page_name": "Sign In", "route": "/login", "page_type": "auth",
         "functions": ["Sign in with the approved identity fields."], "sections": []},
        {"page_name": "Sign Up", "route": "/register", "page_type": "auth",
         "functions": ["Create the approved Patient account."], "sections": []},
    ]

    def test_an_auth_page_does_not_publish_a_table(self):
        """The defect: every patient record was readable by any visitor."""
        self.assertFalse(_public_reads_table(self.AUTH, "patients"))

    def test_a_real_public_page_still_publishes_its_table(self):
        pages = self.AUTH + [
            {"page_name": "Doctor Search", "route": "/doctors", "page_type": "public",
             "functions": ["Browse doctors by specialty"], "sections": []},
        ]
        self.assertTrue(_public_reads_table(pages, "doctors"))
        self.assertFalse(_public_reads_table(pages, "patients"))

    def test_a_page_with_no_type_is_treated_as_public(self):
        pages = [{"page_name": "Menu", "route": "/menu", "functions": ["List dishes"],
                  "sections": []}]
        self.assertTrue(_public_reads_table(pages, "dishes"))


if __name__ == "__main__":
    unittest.main()
