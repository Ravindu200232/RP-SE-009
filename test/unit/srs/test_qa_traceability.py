"""QA evidence reaches the parent SRS, and says what it cannot show.

The risk with this path is not that it fails to run - it is that it succeeds and
records a verification that never happened. The same LLM call serves developer
changes, where adding a requirement is the correct response, so the QA report
has to be unmistakable about what it is: evidence, not a change.

These tests hold the three properties that keep it honest.

  1. A requirement with no evidence is named as unverified. A digest that lists
     only passes teaches the document to claim coverage it does not have.
  2. QA gets its own instruction and the other reporters keep theirs untouched.
  3. The digest survives a round trip to disk, because the build writes it and a
     later transaction reads it.
"""
import json
import tempfile
import unittest
from pathlib import Path

from test import _support  # noqa: F401 - puts the agent packages on the path
from server_modules.srs.qa_change import (
    change_path, clear_change, read_change, traceability_digest, write_change,
)
from srs_agent.app.routers.srs import ParentChange
from srs_agent.app.services.parent_sync import _SOURCE_RULES


def evidence(e2e_covers=("borrow-book",)):
    return {
        "revision": 7,
        "ready": False,
        "scope": {"requirements": [
            {"id": "borrow-book", "description": "A member can borrow an available book",
             "evidence": ["unit", "e2e"]},
            {"id": "waive-fine", "description": "A librarian can waive a fine",
             "evidence": ["unit", "e2e"]},
        ]},
        "suites": [
            {"kind": "unit", "suite": "books.spec", "status": "passed",
             "covers": ["borrow-book", "waive-fine"]},
            {"kind": "e2e", "suite": "borrow.spec", "status": "passed",
             "covers": list(e2e_covers)},
            {"kind": "e2e", "suite": "flaky.spec", "status": "failed",
             "covers": ["waive-fine"]},
        ],
        "coverage": {
            "unit": {"requirementCoverage": {"covered": 2, "total": 2, "percent": 100.0}},
            "e2e": {"covered": 1, "total": 2, "percent": 50.0,
                    "target": 80.0, "status": "below-target"},
        },
        "missingRequirements": [],
        "limitations": {},
    }


class Digest(unittest.TestCase):
    def test_a_requirement_without_evidence_is_named_unverified(self):
        digest = traceability_digest(evidence())
        rows = {r["id"]: r for r in digest["requirements"]}
        self.assertTrue(rows["borrow-book"]["verified"])
        self.assertFalse(rows["waive-fine"]["verified"])
        self.assertIn("NOT VERIFIED", digest["summary_text"])
        self.assertIn("waive-fine", digest["summary_text"].split("NOT VERIFIED")[1])

    def test_a_failed_suite_does_not_count_as_evidence(self):
        """flaky.spec covers waive-fine and failed; it must not verify anything."""
        digest = traceability_digest(evidence())
        row = next(r for r in digest["requirements"] if r["id"] == "waive-fine")
        self.assertNotIn("e2e", row["proved_by"])

    def test_the_shortfall_is_stated(self):
        text = traceability_digest(evidence())["summary_text"]
        self.assertIn("1/2", text)
        self.assertIn("BELOW-TARGET", text)

    def test_the_description_travels_with_the_id(self):
        """Scope ids are build-chosen, so the description is what matches a row."""
        text = traceability_digest(evidence())["summary_text"]
        self.assertIn("A member can borrow an available book", text)
        self.assertIn("A librarian can waive a fine", text)

    def test_everything_verified_reads_as_such(self):
        digest = traceability_digest(evidence(e2e_covers=("borrow-book", "waive-fine")))
        self.assertTrue(all(r["verified"] for r in digest["requirements"]))
        self.assertNotIn("NOT VERIFIED", digest["summary_text"])

    def test_a_build_with_no_scope_says_so(self):
        digest = traceability_digest({"scope": {}, "suites": [], "coverage": {}})
        self.assertEqual(digest["requirements"], [])
        self.assertIn("No verification scope", digest["summary_text"])


class OnDisk(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_change(tmp, evidence(), {"complete": True})
            self.assertEqual(path, change_path(tmp))
            loaded = read_change(tmp)
            self.assertEqual(loaded["revision"], 7)
            self.assertIn("NOT VERIFIED", loaded["summary_text"])

    def test_recording_it_consumes_it(self):
        """Otherwise the next change re-posts this build's evidence as its own."""
        with tempfile.TemporaryDirectory() as tmp:
            write_change(tmp, evidence(), {"complete": True})
            self.assertTrue(read_change(tmp))
            clear_change(tmp)
            self.assertEqual(read_change(tmp), {})
            clear_change(tmp)      # twice is not an error

    def test_absent_is_empty_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(read_change(tmp), {})

    def test_unreadable_is_empty_not_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = change_path(tmp)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("{ not json", encoding="utf-8")
            self.assertEqual(read_change(tmp), {})


class TheRoute(unittest.TestCase):
    def test_qa_is_an_accepted_source(self):
        for source in ("designer", "developer", "design-customizer", "qa"):
            ParentChange(change_id="c1", source=source, summary="x")

    def test_an_unknown_source_is_still_refused(self):
        with self.assertRaises(Exception):
            ParentChange(change_id="c1", source="anything", summary="x")


class TheRule(unittest.TestCase):
    def test_only_qa_carries_the_traceability_restriction(self):
        self.assertIn("qa", _SOURCE_RULES)
        for source in ("designer", "developer", "design-customizer"):
            self.assertEqual(_SOURCE_RULES.get(source, ""), "")

    def test_the_rule_forbids_writing_requirements(self):
        rule = _SOURCE_RULES["qa"].lower()
        self.assertIn("requirement_traceability_matrix", rule)
        for forbidden in ("no functional requirement", "no table", "no role",
                          "no page", "no workflow"):
            self.assertIn(forbidden, rule)


if __name__ == "__main__":
    unittest.main()


class TheMergeItDrives(unittest.TestCase):
    """The digest is also read as an edit instruction. It must not read as one.

    `merge_edit`'s prompt argument is keyword-matched for removal intent, and a
    match makes the patch replace the list rather than fold into it. The QA rule
    used to say "Do NOT add, remove or reword ..." - the word `remove` matched,
    and a report covering 9 scope buckets replaced a 76-row traceability matrix
    with 39 rows. A report that says "nothing was removed" must not be read as
    "remove things".
    """

    def digest_text(self):
        return traceability_digest(evidence())["summary_text"]

    def test_the_digest_does_not_read_as_a_removal_instruction(self):
        from srs_agent.app.agents.customization import _REMOVAL
        found = _REMOVAL.search(self.digest_text())
        self.assertIsNone(found, f"digest still reads as removal: {found and found.group(0)}")

    def test_a_shorter_patch_does_not_shrink_the_matrix(self):
        from srs_agent.app.agents.customization import merge_edit
        srs = {"srs_document": {"requirement_traceability_matrix": [
            {"requirement_id": f"FR-{n:03d}", "verification_status": ""} for n in range(1, 77)]}}
        patch = {"requirement_traceability_matrix": [
            {"requirement_id": "FR-002", "verification_status": "Verified"}]}
        merged = merge_edit(srs, patch, self.digest_text())
        rows = merged["srs_document"]["requirement_traceability_matrix"]
        self.assertEqual(len(rows), 76, "the QA report deleted rows it never mentioned")
        by_id = {r["requirement_id"]: r for r in rows}
        self.assertEqual(by_id["FR-002"]["verification_status"], "Verified")
        self.assertEqual(by_id["FR-003"]["verification_status"], "",
                         "a row the report did not mention must keep its status")

    def test_no_agent_summary_is_read_as_an_edit_instruction(self):
        """No source may: a developer summary shrank the matrix the same way."""
        import inspect
        from srs_agent.app.services import parent_sync
        source = inspect.getsource(parent_sync.synchronize)
        self.assertIn('edit_intent = ""', source)
        self.assertNotIn("merge_edit(srs, result.get(\"srs_document\"), summary)", source)
