import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.analysis import (AnalyzerAgent, AnalyzerReport, BugFixerAgent,
                             Finding, FixVerdict, Reproduction)
from agents.analysis.analyzer import REPAIRABLE_MAJOR
from qa_agent.e2e.e2e_execution import E2EExecutionMixin


class FakeArch:
    STRAY_DIRECTIVE_RE = __import__("re").compile(r"['\"]use client['\"]")
    NEXT_PROTECTED = frozenset()

    def __init__(self, root, plan=None, plan_md="", reply=""):
        self.project_dir = Path(root)
        self.plan = plan or {}
        self.plan_md = plan_md
        self.files = {}
        self.write_seq = 0
        self.num_ctx = 32768
        self.reply = reply
        self.stream_calls = 0

    def imported_packages(self, _body): return []
    def lint_generated(self): return []
    def _stream(self, _messages, sink, **_kwargs):
        self.stream_calls += 1
        sink(self.reply)
    def _builder_sys(self): return "Write complete files only."
    def _safe_path(self, rel): return self.project_dir / rel
    def write_file(self, rel, body):
        target = self.project_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        self.files[rel] = body
        self.write_seq += 1
        return True
    def repair_missing_imports(self): return None
    def sync_dependencies(self): return None


def write(root, rel, body):
    target = Path(root) / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")


class RouteLookupTests(unittest.TestCase):
    def test_a_literal_route_wins_over_a_dynamic_sibling(self):
        """`[roomId]` sorts before `available`, so first-match found the wrong one.

        The live GET handler was then reported as unserved, and every repair
        round rewrote a file that had nothing wrong with it.
        """
        routes = {
            "/api/rooms/[roomId]": {"file": "app/api/rooms/[roomId]/route.js",
                                    "methods": ["PATCH"], "kind": "api"},
            "/api/rooms/available": {"file": "app/api/rooms/available/route.js",
                                     "methods": ["GET"], "kind": "api"},
        }

        served = AnalyzerAgent._route_for("/api/rooms/available", routes)
        self.assertEqual(served["file"], "app/api/rooms/available/route.js")
        self.assertIn("GET", served["methods"])

        # A real id still falls through to the dynamic handler.
        dynamic = AnalyzerAgent._route_for("/api/rooms/507f1f77bcf86cd799439011",
                                           routes)
        self.assertEqual(dynamic["file"], "app/api/rooms/[roomId]/route.js")


class AnalyzerRefactorTests(unittest.TestCase):
    def test_public_join_surface_and_line_ceiling(self):
        self.assertTrue(REPAIRABLE_MAJOR)
        self.assertTrue(issubclass(BugFixerAgent, object))
        self.assertTrue(issubclass(FixVerdict, object))
        self.assertTrue(issubclass(Reproduction, object))
        folder = Path(__file__).parents[3] / "agents" / "analysis"
        py = sorted(folder.glob("*.py"))
        self.assertEqual([p.name for p in py],
                         ["__init__.py", "analyzer.py", "bugfixer_apply.py",
                          "reproduce.py"])
        nonempty = sum(sum(bool(line.strip()) for line in p.read_text(
            encoding="utf-8").splitlines()) for p in py)
        self.assertLess(nonempty, 1800)

    def test_better_auth_invariants_cover_missing_page_seed_and_origins(self):
        with tempfile.TemporaryDirectory() as root:
            write(root, "app/page.jsx",
                  "import Link from 'next/link'; export default function P(){return <Link href='/sign-in'>Sign in</Link>}")
            write(root, "lib/auth.js",
                  "import { betterAuth } from 'better-auth'; export const auth = betterAuth({trustedOrigins:['http://localhost:*']})")
            write(root, "lib/seed.js",
                  "export async function ensureSeeded(){ await users.insertOne({email:'admin@example.com'}) }")
            write(root, "app/api/auth/[...all]/route.js",
                  "import { toNextJsHandler } from 'better-auth/next-js'; import { auth } from '@/lib/auth'; export const { GET, POST } = toNextJsHandler(auth)")
            plan = {"roles_and_access": {"signup": "open"}, "demo_accounts": [
                {"email": "admin@example.com", "password": "Password1!", "role": "admin"},
                {"email": "guest@example.com", "password": "Password1!", "role": "guest"}],
                "workflows": [{"name": "Admin", "who": "ROLE admin"},
                              {"name": "Guest", "who": "role-guest"}]}
            agent = AnalyzerAgent(FakeArch(root, plan=plan), root)
            codes = {f.code for f in agent._auth_invariants()}
            self.assertTrue({"BETTER_AUTH_DEMO_SEED", "AUTH_ORIGIN",
                             "AUTH_PAGE_MISSING", "AUTH_SIGNUP_MISSING"} <= codes)
            role_messages = "\n".join(f.message for f in agent.role_contract_findings())
            self.assertNotIn("roleadmin", role_messages)
            self.assertNotIn("roleguest", role_messages)

            write(root, "app/sign-up/page.jsx",
                  "'use client'; import { signUp } from '@/lib/auth-client'; "
                  "export default function Page(){ return signUp.email }" )
            complete = AnalyzerAgent(FakeArch(root, plan=plan), root)
            self.assertNotIn("AUTH_SIGNUP_MISSING",
                             {f.code for f in complete._auth_invariants()})

    def test_semantic_json_requires_exact_plan_and_source_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            body = "export default function Page(){return <main>No booking action</main>}"
            write(root, "app/page.jsx", body)
            plan = {"capabilities": [{"id": "CAP-001", "requirement":
                                      "Guests can book a room.",
                                      "files": ["app/page.jsx"]}]}
            reply = json.dumps({"status": "complete", "findings": [{
                "severity": "major", "code": "UNBUILT_PROMISE",
                "message": "The booking action is absent.",
                "path": "app/page.jsx", "fix": "Add the planned flow.",
                "plan_quote": "Guests can book a room.",
                "evidence": [{"path": "app/page.jsx",
                              "quote": "No booking action"}]}]})
            arch = FakeArch(root, plan=plan,
                            plan_md="Guests can book a room.", reply=reply)
            arch.files = {"app/page.jsx": body}
            agent = AnalyzerAgent(arch, root)
            findings = agent._semantic_lens("capabilities", AnalyzerReport(
                routes=agent.enumerate_routes()))
            self.assertEqual([f.code for f in findings], ["UNBUILT_PROMISE"])
            arch.reply = reply.replace("No booking action", "invented source")
            self.assertEqual(agent._semantic_lens("capabilities",
                             AnalyzerReport(routes=agent.enumerate_routes())), [])

    def test_legacy_semantic_methods_share_validated_cached_lens(self):
        with tempfile.TemporaryDirectory() as root:
            body = "export default function Page(){return <main>No booking action</main>}"
            write(root, "app/page.jsx", body)
            plan = {"capabilities": [{"id": "CAP-001", "requirement":
                                      "Guests can book a room.",
                                      "files": ["app/page.jsx"]}]}
            reply = json.dumps({"status": "complete", "findings": [{
                "severity": "major", "code": "UNBUILT_PROMISE",
                "message": "The planned chain is absent.",
                "path": "app/page.jsx", "fix": "Connect the accepted flow.",
                "plan_quote": "Guests can book a room.",
                "evidence": [{"path": "app/page.jsx",
                              "quote": "No booking action"}]}]})
            arch = FakeArch(root, plan=plan,
                            plan_md="Guests can book a room.", reply=reply)
            arch.files = {"app/page.jsx": body}
            agent = AnalyzerAgent(arch, root)
            first = agent.planned_data_findings()
            again = agent.planned_data_findings()
            workflow = agent.workflow_control_findings()
            self.assertEqual(first[0].code, "MISSING_PLANNED_DATA")
            self.assertEqual(again[0].code, "MISSING_PLANNED_DATA")
            self.assertEqual(workflow[0].code, "MISSING_WORKFLOW_CONTROL")
            self.assertEqual(arch.stream_calls, 2)

    def test_decidable_compatibility_checks_are_not_silent_stubs(self):
        with tempfile.TemporaryDirectory() as root:
            write(root, "app/layout.jsx",
                  "export default async function Layout({children}){await ensureSeeded();return <><Navbar/>{children}</>}")
            write(root, "app/page.jsx",
                  "import Card from '@/components/Card'; export default function Page(){return <Card />} ")
            write(root, "app/sign-in/page.jsx",
                  "export default function SignIn(){return <p>Demo Accounts admin@example.com Password1!</p>}")
            write(root, "components/Card.jsx",
                  "export default function Card({ item }){return <p>{item.name}</p>}")
            write(root, "lib/seed.js",
                  "export async function ensureSeeded(){return Array.from({ length: 8 }, (_,i)=>({i}))}")
            plan = {"demo_accounts": [{"email": "admin@example.com",
                                       "password": "Password1!",
                                       "role": "admin"}]}
            agent = AnalyzerAgent(FakeArch(root, plan=plan), root)
            self.assertTrue(agent.prop_contract_breaks())
            self.assertTrue(agent.credentials_exposed())
            self.assertTrue(agent.seed_volume())
            self.assertTrue(agent.layout_chrome())
            codes = {f.code for f in agent.scan().findings}
            self.assertTrue({"PROP_CONTRACT", "CREDS_IN_UI", "SEED_VOLUME",
                             "SEED_IN_LAYOUT"} <= codes)
            self.assertNotIn("LAYOUT_CHROME", codes)  # the shell is planned now

    def test_generated_e2e_syntax_is_a_blocker(self):
        with tempfile.TemporaryDirectory() as root:
            write(root, "tests/e2e/admin.spec.js",
                  "expect(page).toHaveURL(/admin/rooms/)")
            agent = AnalyzerAgent(FakeArch(root), root)
            with patch("agents.analysis.analyzer.check_syntax", return_value=([
                    {"path": "tests/e2e/admin.spec.js", "line": 1,
                     "message": "Expected ')'"}], "")):
                findings = agent.e2e_syntax_findings()
            self.assertEqual(findings[0].code, "E2E_SYNTAX")

    def test_e2e_execution_stops_before_browser_on_syntax_failure(self):
        finding = Finding("blocker", "E2E_SYNTAX", "invalid regex",
                          "tests/e2e/admin.spec.js")

        class Analyzer:
            def e2e_syntax_findings(self, paths):
                self.paths = paths
                return [finding]

        class Runner(E2EExecutionMixin):
            az = Analyzer()

        class Scenario:
            def spec_path(self): return "tests/e2e/admin.spec.js"

        failures = Runner().run(Scenario())
        self.assertEqual(failures[0].kind, "SYNTAX")
        self.assertIn("invalid regex", failures[0].message)


DESCRIBED = """\
import { render, screen } from '@testing-library/react'
import Navbar from '@/components/Navbar'

describe('Navbar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows user links when logged in as user', () => {
    render(<Navbar />)
    expect(screen.getByText('Guest User')).toBeInTheDocument()
  })

  it('toggles mobile menu', () => {
    render(<Navbar />)
    expect(screen.getByRole('link', { name: /rooms/i })).toBeInTheDocument()
  })
})
"""


class FailingCaseNameTests(unittest.TestCase):
    """Vitest reports `fullName`; the source says `it(title)`.

    A case inside `describe('Navbar')` is reported as `Navbar toggles mobile
    menu`, so the failing set never intersected the titles `_case_blocks`
    reads. `_splice_passing` therefore treated the failing case as passing and
    put its OLD body back over the repair, keeping only the shared module scope
    from the rewrite — the one change that can break a case the round was not
    about. That is the whole shape of the thrashing repair loop: a round that
    cannot fix its target and can only break its neighbours.
    """

    # What vitest wrote for these two cases, verbatim in shape.
    FAILING = ["Navbar toggles mobile menu"]

    def test_the_repair_to_the_failing_case_survives_the_splice(self):
        new = DESCRIBED.replace(
            "expect(screen.getByRole('link', { name: /rooms/i })).toBeInTheDocument()",
            "expect(screen.getAllByRole('link', { name: /rooms/i })).toHaveLength(2)")
        spliced = BugFixerAgent._splice_passing(DESCRIBED, new, self.FAILING)
        self.assertIn("toHaveLength(2)", spliced)

    def test_a_passing_case_is_still_restored_byte_for_byte(self):
        new = DESCRIBED.replace("expect(screen.getByText('Guest User')).toBeInTheDocument()",
                                "expect(true).toBe(true)")
        spliced = BugFixerAgent._splice_passing(DESCRIBED, new, self.FAILING)
        self.assertIn("expect(screen.getByText('Guest User')).toBeInTheDocument()",
                      spliced)
        self.assertNotIn("expect(true).toBe(true)", spliced)

    def test_renaming_the_failing_case_is_not_read_as_dropping_a_passing_one(self):
        renamed = DESCRIBED.replace("it('toggles mobile menu'",
                                    "it('opens the mobile menu'")
        self.assertEqual(
            BugFixerAgent._lost_cases(DESCRIBED, renamed, self.FAILING), "")

    def test_dropping_a_genuinely_passing_case_is_still_refused(self):
        without = DESCRIBED.replace(
            "  it('shows user links when logged in as user', () => {\n"
            "    render(<Navbar />)\n"
            "    expect(screen.getByText('Guest User')).toBeInTheDocument()\n"
            "  })\n\n", "")
        self.assertIn("drops passing cases",
                      BugFixerAgent._lost_cases(DESCRIBED, without, self.FAILING))

    def test_the_longest_title_wins_so_a_short_sibling_is_not_swept_up(self):
        titles = ["b", "a b"]
        self.assertEqual(BugFixerAgent._failing_titles(titles, ["Suite a b"]),
                         {"a b"})

    def test_a_case_reported_by_full_name_is_still_found_in_its_file(self):
        self.assertTrue(
            BugFixerAgent.has_case(DESCRIBED, "Navbar toggles mobile menu"))
        self.assertFalse(
            BugFixerAgent.has_case(DESCRIBED, "Navbar renders a footer"))


if __name__ == "__main__":
    unittest.main()
