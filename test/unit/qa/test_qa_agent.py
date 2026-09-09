"""What the QA agent proves, and how it writes it down.

The stages themselves need a model and a browser, so what is tested here is
everything around them: making the runner work, reading the runner's own
report rather than a summary of it, deciding when repair has stopped making
progress, and producing the record the studio renders.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test import _support  # noqa: F401
from qa_agent import e2e, harness, report, security, unit


class ContextHandoffTests(unittest.TestCase):
    def test_qa_keeps_builder_reads_and_evidence_while_using_its_own_model(self):
        from builder_agent.memory import Memory
        from qa_agent.agent import QAAgent

        with tempfile.TemporaryDirectory() as directory:
            memory = Memory()
            memory.add_user("PriceEditor already reads cents; guest journey passed.")
            memory.evidence.define_scope("web", "nextjs-mongo", [
                {"id": "price", "description": "Update room prices", "evidence": ["unit"]}
            ], unit_target=80)
            with patch("builder_agent.agent.Router.context_window", return_value=1_048_576):
                qa = QAAgent(project="hotel", project_dir=directory, model="qa-model",
                             memory=memory)
            self.assertIs(qa.agent.memory, memory)
            self.assertEqual(qa.agent.router.model, "qa-model")
            loop = qa.agent._loop(qa.agent.registry, verification_kinds=("unit",))
            loop._refresh_system()
            self.assertIn("PriceEditor already reads cents", str(memory.build()))
            self.assertEqual(memory.evidence.scope["requirements"][0]["id"], "price")
            self.assertFalse(memory.evidence.summary()["coverage"]["unit"]["required"])
            self.assertEqual(memory.budget_tokens, 1_048_576)


class BuildEvidenceReportTests(unittest.TestCase):
    def test_existing_unit_and_e2e_results_make_a_report_without_reexecuting(self):
        evidence = {"ready": True, "suites": [
            {"kind": "unit", "suite": "all", "status": "passed", "sequence": 1,
             "output": " Test Files  2 passed (2)\n Tests  8 passed | 1 skipped (9)\n"},
            {"kind": "e2e", "suite": "book", "status": "passed",
             "output": "1. navigate -> /\n2. assert textIncludes -> Saved"}
        ]}
        with tempfile.TemporaryDirectory() as directory, \
                patch("subprocess.run", side_effect=AssertionError("No second test run")):
            result = report.from_evidence(project="demo", project_dir=Path(directory),
                evidence=evidence, security={"findings": []}, complete=True)
        self.assertEqual(result["vitest"]["numPassedTests"], 8)
        self.assertEqual(result["vitest"]["numPendingTests"], 1)
        self.assertNotIn("testResults", result["vitest"])  # no invented assertion rows
        self.assertEqual(result["report"]["e2e"]["stage_passed"], 2)

    def test_stale_evidence_is_not_relabelled_as_current_passing_tests(self):
        with tempfile.TemporaryDirectory() as directory:
            result = report.from_evidence(project="demo", project_dir=Path(directory),
                evidence={"suites": [{"kind": "unit", "status": "outdated",
                                     "output": "Tests 9 passed (9)"}]},
                security={"findings": []}, complete=False)
        self.assertIsNone(result["vitest"])
        self.assertFalse(result["complete"])


def vitest_report(cases):
    """A Vitest JSON report with the given (file, name, status) rows."""
    suites = {}
    for path, name, status in cases:
        suites.setdefault(path, []).append(
            {"fullName": name, "status": status,
             "failureMessages": ["Cannot find module '@/lib/missing'"]
             if status == "failed" else []})
    return {"testResults": [{"name": path, "assertionResults": rows}
                            for path, rows in suites.items()]}


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "package.json").write_text(
            json.dumps({"name": "app", "scripts": {}}), encoding="utf-8")
        self.commands = []

    def run_command(self, command):
        self.commands.append(command)
        return {"exitCode": 0}

    def test_a_project_without_a_runner_is_made_runnable_before_anything_else(self):
        result = harness.prepare(self.root, self.run_command)

        self.assertTrue(result["ok"])
        manifest = json.loads((self.root / "package.json").read_text(encoding="utf-8"))
        self.assertIn("vitest", manifest["devDependencies"])
        self.assertIn("@vitest/coverage-v8", manifest["devDependencies"])
        self.assertEqual(manifest["scripts"]["test"], "vitest run")
        self.assertTrue((self.root / "vitest.config.js").is_file())
        self.assertTrue((self.root / "vitest.setup.js").is_file())
        self.assertEqual(self.commands, ["npm install"])

    def test_a_config_without_coverage_is_repaired_not_left_to_fail_later(self):
        (self.root / "vitest.config.js").write_text("export default {}", encoding="utf-8")

        harness.prepare(self.root, self.run_command)

        self.assertIn("coverage", (self.root / "vitest.config.js").read_text(encoding="utf-8"))

    def test_a_failed_install_is_reported_rather_than_silently_continued(self):
        result = harness.prepare(self.root, lambda c: {"exitCode": 1, "stderr": "ENOENT"})

        self.assertFalse(result["ok"])
        self.assertIn("install failed", result["reason"])

    def test_a_project_with_no_manifest_is_not_something_to_test(self):
        empty = Path(tempfile.mkdtemp())
        result = harness.prepare(empty, self.run_command)

        self.assertFalse(result["ok"])
        self.assertIn("package.json", result["reason"])

    def test_the_run_command_asks_for_both_reports_the_stage_reads(self):
        command = harness.run_command(self.root)

        self.assertIn("--coverage", command)
        self.assertIn("--reporter=json", command)
        self.assertIn(".agentforge/qa/vitest.json", command)

    def test_the_package_manager_is_taken_from_the_lockfile_that_is_there(self):
        self.assertEqual(harness.package_manager(self.root), "npm")
        (self.root / "pnpm-lock.yaml").write_text("", encoding="utf-8")
        self.assertEqual(harness.package_manager(self.root), "pnpm")


class UnitStageTests(unittest.TestCase):
    def test_counts_come_from_the_assertion_rows_not_the_summary(self):
        # The summary fields go stale after a targeted repair run; reporting
        # them is how a red suite gets shown as green.
        raw = vitest_report([("test/a.test.js", "one", "passed"),
                             ("test/a.test.js", "two", "failed"),
                             ("test/b.test.js", "three", "skipped")])
        raw["numPassedTests"] = 99

        counts = unit.counts_of(raw)

        self.assertEqual(counts, {"passed": 1, "failed": 1, "skipped": 1,
                                  "total": 3, "files": 2})

    def test_a_missing_report_is_zero_rather_than_a_crash(self):
        self.assertEqual(unit.counts_of(None)["total"], 0)
        self.assertEqual(unit.failures_of(None), [])

    def test_the_same_failures_twice_are_recognised_as_no_progress(self):
        raw = vitest_report([("test/a.test.js", "one", "failed")])
        first = unit.signature(unit.failures_of(raw))
        second = unit.signature(unit.failures_of(raw))

        self.assertEqual(first, second)
        self.assertNotEqual(first, unit.signature(unit.failures_of(
            vitest_report([("test/a.test.js", "different", "failed")]))))

    def test_line_numbers_do_not_make_the_same_failure_look_new(self):
        one = [{"file": "a.js", "case": "x", "message": "AssertionError at line 12"}]
        two = [{"file": "a.js", "case": "x", "message": "AssertionError at line 44"}]
        self.assertEqual(unit.signature(one), unit.signature(two))

    def test_failures_are_grouped_so_the_round_summary_says_something(self):
        failures = [
            {"file": "a.js", "case": "one", "message": "Cannot find module '@/x'"},
            {"file": "b.js", "case": "two", "message": "Cannot find module '@/y'"},
            {"file": "c.js", "case": "three", "message": "expected 1 to be 2"},
        ]

        top = unit.top_classes(failures)

        self.assertEqual(top[0], {"class": "missing module", "count": 2})
        self.assertIn({"class": "assertion", "count": 1}, top)

    def test_each_failure_kind_is_named_rather_than_lumped_together(self):
        self.assertEqual(unit.classify("MongoServerSelectionError: connect ECONNREFUSED"),
                         "database")
        self.assertEqual(unit.classify("Test timed out in 5000ms"), "timeout")
        self.assertEqual(unit.classify("SyntaxError: Unexpected token"), "syntax")
        self.assertEqual(unit.classify("something else entirely"), "other")

    def test_a_note_about_a_suspected_bug_is_collected_not_asserted(self):
        root = Path(tempfile.mkdtemp())
        (root / "test").mkdir()
        (root / "test/a.test.js").write_text(
            "// SUSPECT: the total ignores tax, which looks wrong\n"
            "it('adds', () => {})\n", encoding="utf-8")

        suspects = unit._suspects(root)

        self.assertEqual(len(suspects), 1)
        self.assertIn("ignores tax", suspects[0]["note"])


class E2EStageTests(unittest.TestCase):
    def test_a_passing_journey_scores_every_stage(self):
        journeys = e2e.journeys_from_evidence({"suites": [{
            "kind": "e2e", "suite": "login", "status": "passed",
            "output": "1. navigate -> /login\n2. type email\n3. click Sign in"}]})

        self.assertEqual(journeys[0].score(),
                         {"stage_total": 3, "stage_passed": 3,
                          "stage_failed": 0, "stage_not_reached": 0})

    def test_the_stage_the_reason_blames_is_the_one_marked_failed(self):
        journeys = e2e.journeys_from_evidence({"suites": [{
            "kind": "e2e", "suite": "checkout", "status": "failed",
            "reason": "Step 2 failed: no Pay button",
            "output": "1. navigate -> /cart\n2. click Pay\n3. assert textIncludes"}]})
        stages = journeys[0].as_dict()["stages"]

        self.assertEqual([s["status"] for s in stages],
                         ["passed", "failed", "not_reached"])

    def test_a_failure_with_no_step_number_still_marks_something_failed(self):
        journeys = e2e.journeys_from_evidence({"suites": [{
            "kind": "e2e", "suite": "x", "status": "failed",
            "reason": "the page reported problems",
            "output": "1. navigate -> /\n2. assert noDiagnostics"}]})

        self.assertEqual(journeys[0].score()["stage_failed"], 1)

    def test_only_journeys_are_read_from_the_ledger(self):
        journeys = e2e.journeys_from_evidence({"suites": [
            {"kind": "unit", "suite": "logic", "status": "passed", "output": "1. x"},
            {"kind": "e2e", "suite": "login", "status": "passed", "output": "1. x"}]})

        self.assertEqual([j.title for j in journeys], ["login"])

    def test_the_report_totals_stages_across_every_journey(self):
        result = e2e.E2EResult(ran=True, journeys=e2e.journeys_from_evidence({"suites": [
            {"kind": "e2e", "suite": "a", "status": "passed", "output": "1. x\n2. y"},
            {"kind": "e2e", "suite": "b", "status": "failed", "reason": "Step 1 failed: no",
             "output": "1. x\n2. y"}]}))

        rendered = result.as_report()

        self.assertEqual(rendered["total"], 2)
        self.assertEqual(rendered["passed"], 1)
        self.assertEqual(rendered["stage_total"], 4)
        self.assertEqual(rendered["stage_passed"], 2)
        self.assertEqual(rendered["stage_not_reached"], 1)
        self.assertEqual(rendered["rate"], 50)


class SecurityScanTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def write(self, relative, body):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    def codes(self):
        return {finding["code"] for finding in security.scan(self.root)}

    def test_a_public_write_handler_does_not_invent_an_authentication_requirement(self):
        self.write("app/api/books/[id]/route.js",
                   "export async function PATCH(req) { return Response.json({ read: true }) }")
        self.assertEqual(security.scan(self.root), [])

    def test_a_write_handler_that_checks_the_session_is_not_reported(self):
        self.write("app/api/admin/route.js",
                   "import { getServerSession } from 'next-auth';\n"
                   "export async function POST(req) {\n"
                   "  const session = await getServerSession();\n"
                   "  if (!session) return new Response(null, { status: 401 });\n"
                   "  return Response.json({});\n}")
        self.assertNotIn("UNGUARDED_ROUTE", self.codes())

    def test_a_read_only_handler_is_not_treated_as_a_write(self):
        self.write("app/api/rooms/route.js",
                   "export async function GET() { return Response.json([]) }")
        self.assertNotIn("UNGUARDED_ROUTE", self.codes())

    def test_a_dashboard_name_does_not_imply_private_data_or_accounts(self):
        self.write("app/dashboard/page.jsx", "export default function Weather(){ return null }")
        self.assertEqual(security.scan(self.root), [])

    def test_a_public_page_is_not_expected_to_guard_itself(self):
        self.write("app/page.jsx", "export default function Home(){ return null }")
        self.assertNotIn("UNGUARDED_PAGE", self.codes())

    def test_a_secret_behind_a_public_variable_is_reported(self):
        self.write("lib/api.js", "const key = process.env.NEXT_PUBLIC_STRIPE_SECRET;")
        self.assertIn("EXPOSED_SECRET", self.codes())

    def test_a_public_variable_that_is_not_a_secret_is_left_alone(self):
        self.write("lib/api.js", "const url = process.env.NEXT_PUBLIC_SITE_URL;")
        self.assertNotIn("EXPOSED_SECRET", self.codes())

    def test_a_password_stored_without_hashing_is_reported(self):
        self.write("app/api/signup/route.js",
                   "export async function POST(req){ const body = await req.json();\n"
                   "  await User.create({ password: body.password }) }")
        self.assertIn("FAKE_HASH", self.codes())

    def test_a_hashed_password_is_not_reported(self):
        self.write("app/api/signup/route.js",
                   "import bcrypt from 'bcrypt';\n"
                   "export async function POST(req){ const body = await req.json();\n"
                   "  await User.create({ password: body.password }) }")
        self.assertNotIn("FAKE_HASH", self.codes())

    def test_unsafe_html_and_injection_are_reported(self):
        self.write("components/Bio.jsx", "<div dangerouslySetInnerHTML={{__html: bio}} />")
        self.write("lib/find.js", "const rows = await Model.find({ $where: input })")
        codes = self.codes()
        self.assertIn("UNSAFE_HTML", codes)
        self.assertIn("QUERY_INJECTION", codes)

    def test_the_project_s_own_tests_and_dependencies_are_not_scanned(self):
        self.write("node_modules/evil/index.js",
                   "const k = process.env.NEXT_PUBLIC_API_SECRET;")
        self.write("test/a.test.js", "const k = process.env.NEXT_PUBLIC_API_SECRET;")
        self.assertEqual(security.scan(self.root), [])

    def test_every_finding_names_a_file_and_a_line(self):
        self.write("lib/api.js", "const a = 1;\nconst key = process.env.NEXT_PUBLIC_API_SECRET;")
        finding = security.scan(self.root)[0]

        self.assertEqual(finding["file"], "lib/api.js")
        self.assertEqual(finding["line"], 2)
        self.assertIn(finding["code"], security.CHECKS)

    def test_an_unavailable_audit_is_empty_rather_than_an_error(self):
        self.assertEqual(security.audit(self.root, lambda c: {"stdout": "not json"}), {})


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.unit = unit.UnitResult(
            ran=True,
            report=vitest_report([("test/a.test.js", "one", "passed"),
                                  ("test/a.test.js", "two", "failed")]),
            rounds=[{"round": 1, "rate": 50, "floor": 95, "passed": 1, "cases": 2, "top": []}],
            unresolved=[{"file": "test/a.test.js", "case": "two",
                         "message": "boom", "diagnosis": "assertion"}])
        self.e2e = e2e.E2EResult(ran=True, journeys=e2e.journeys_from_evidence({"suites": [
            {"kind": "e2e", "suite": "login", "status": "passed", "output": "1. x\n2. y"}]}))

    def record(self):
        return report.assemble(
            project="demo", project_dir=self.root, unit=self.unit, e2e=self.e2e,
            security={"findings": [], "audit": {}},
            evidence={"ready": False, "suites": [], "revision": 1},
            runtime=[], manifest={"test/a.test.js": {"target": "app/api/x/route.js"}},
            tests={"test/a.test.js": "it('one', () => {})"}, history=[])

    def test_the_record_is_the_shape_the_studio_reads(self):
        record = self.record()

        # Every one of these is dereferenced by a Testing tab view.
        self.assertIn("vitest", record)
        self.assertIn("testResults", record["vitest"])
        for key in ("unit", "suite", "e2e", "runtime", "security", "evidence"):
            self.assertIn(key, record["report"])
        self.assertIn("stage_total", record["report"]["e2e"])
        self.assertIn("unresolved", record["report"]["suite"])
        self.assertIn("scores", record["performance"])

    def test_reading_back_what_was_written_returns_the_same_record(self):
        report.write(self.root, self.record())

        loaded = report.read(self.root, "demo")

        self.assertEqual(loaded["project"], "demo")
        self.assertEqual(loaded["report"]["e2e"]["stage_total"], 2)

    def test_a_project_with_no_record_says_so_rather_than_looking_empty(self):
        loaded = report.read(Path(tempfile.mkdtemp()), "nothing")

        self.assertIn("error", loaded)
        self.assertEqual(loaded["project"], "nothing")

    def test_history_keeps_the_first_round_of_each_run_only(self):
        # Later rounds measure repair, not what the generated tests did on
        # their own; mixing them makes the trend meaningless.
        history = report.append_history({"history": [{"round": 1, "rate": 30}]},
                                        [{"round": 1, "rate": 50}, {"round": 2, "rate": 90}])

        self.assertEqual([row["rate"] for row in history], [30, 50])

    def test_the_pdf_renders_the_same_evidence(self):
        out = report.build_pdf(self.record(), self.root / "qa" / "Test_Report.pdf", "demo")

        self.assertTrue(out.is_file())
        self.assertGreater(out.stat().st_size, 1000)
        self.assertEqual(out.read_bytes()[:4], b"%PDF")


if __name__ == "__main__":
    unittest.main()
