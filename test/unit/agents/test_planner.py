"""Contracts for the unified LLM planner and its legacy QA views."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agents.planner.architecture import FileStreamParser
from agents.planner.build_templates import render_templates
from agents.planner.planning import PlannerAgent


def _model_plan() -> dict:
    return {
        "project": {
            "name": "stock-desk",
            "title": "Stock Desk",
            "summary": "A compact inventory workspace.",
            "product_type": "dashboard",
            "primary_goal": "Track products",
            "target_audiences": ["manager"],
            "success_metrics": ["A product can be created and found"],
        },
        "requirements": [{
            "id": "REQ-001",
            "source_text": "Managers can add products.",
            "actor": "manager",
            "behavior": "Create a product",
            "acceptance": ["The saved product appears in inventory"],
        }],
        "design": {"direction": "quiet operational dashboard"},
        "information_architecture": {"navigation_model": "top navigation"},
        "site_map": [
            {"path": "/", "parent": "", "label": "Home", "purpose": "Overview"},
            {"path": "/products", "parent": "/", "label": "Products",
             "purpose": "Manage inventory", "reached_from": ["Products link"]},
        ],
        "routes": [
            {"path": "/", "file": "app/page.jsx", "purpose": "Overview"},
            {"path": "/products", "file": "app/products/page.jsx",
             "purpose": "Manage inventory", "requirement_ids": ["REQ-001"]},
        ],
        "data_model": [],
        "roles_and_access": {
            "authentication_required": False,
            "roles": [{"name": "manager", "home": "/products"}],
        },
        "api_contracts": [],
        "capabilities": [{
            "id": "CAP-001", "actor": "manager", "behavior": "Create a product",
            "proof": ["Submit the form", "See the saved row"],
            "files": ["app/products/page.jsx"], "route": "/products",
        }],
        "architecture": {"rendering_strategy": "server-first"},
        "e2e_plan": {
            "strategy": "walk every capability",
            "journeys": [{
                "id": "E2E-001", "name": "Create product", "actor": "manager",
                "start_path": "/products", "capability_ids": ["CAP-001"],
                "steps": [{"at": "/products", "action": "submit product form",
                           "expect": "saved product row is visible"}],
                "final_assertion": "Product remains visible",
            }],
        },
        "file_plan": [{"path": "app/products/page.jsx", "purpose": "Inventory UI"}],
        "tasks": [{"id": 1, "title": "Inventory", "goal": "Build inventory",
                   "files": ["app/products/page.jsx"], "requirement_ids": ["REQ-001"]}],
        "dependencies": [],
        "definition_of_done": ["E2E journey passes"],
    }


class UnifiedPlannerTests(unittest.TestCase):
    def test_one_model_answer_produces_all_planning_artifacts(self):
        calls = []

        def stream(messages, on_delta, **_kwargs):
            calls.append(messages)
            on_delta("```json\n" + json.dumps(_model_plan()) + "\n```")

        planner = PlannerAgent(None, "test-model", stream=stream)
        bundle = planner.create("Managers can add products.")

        self.assertIsNotNone(bundle)
        self.assertEqual(len(calls), 1)
        self.assertIn("Managers can add products.", calls[0][1]["content"])
        self.assertIn("## Site Map", bundle.markdown)
        self.assertIn("## End-to-End Plan", bundle.markdown)
        self.assertIn("# Architecture", bundle.architecture_markdown)
        self.assertIn("# Product Design", bundle.design_markdown)

    def test_rich_capability_keeps_legacy_qa_shape(self):
        plan = PlannerAgent(None, "test-model").normalize(
            _model_plan(), "Managers can add products.")
        capability = plan["capabilities"][0]

        self.assertEqual(capability["who"], "manager")
        self.assertEqual(capability["proof"], "Submit the form; See the saved row")
        self.assertEqual(capability["proof_points"],
                         ["Submit the form", "See the saved row"])
        self.assertEqual(plan["workflows"][0]["covers"], ["CAP-001"])
        self.assertTrue(any(contract["kind"] == "navigation"
                            and contract["target"] == "/products"
                            for contract in plan["contracts"]))

    def test_templates_contain_only_platform_defaults(self):
        plan = PlannerAgent(None, "test-model").normalize(_model_plan())
        files = render_templates("next", plan, mongo_uri="mongodb://localhost/test",
                                 db_name="test", dev_port=3000)

        self.assertIn("package.json", files)
        self.assertIn("lib/mongodb.js", files)
        self.assertNotIn("app/products/page.jsx", files)
        self.assertNotIn("lib/auth.js", files)

    def test_auth_templates_are_self_contained(self):
        raw = _model_plan()
        raw["roles_and_access"]["authentication_required"] = True
        plan = PlannerAgent(None, "test-model").normalize(raw)
        files = render_templates("next", plan, mongo_uri="mongodb://localhost/test",
                                 db_name="test", dev_port=3000)

        self.assertIn("lib/auth.js", files)
        self.assertNotIn("auth-config", files["lib/auth.js"])
        self.assertNotIn("auth-config", files["app/api/auth/[...all]/route.js"])
        self.assertIn('"http://localhost:*"', files["lib/auth.js"])
        self.assertIn('"http://127.0.0.1:*"', files["lib/auth.js"])
        self.assertIn("auth.api.signUpEmail", files["lib/auth.js"])
        self.assertIn("ensureDemoAccounts", files["app/api/auth/[...all]/route.js"])

    def test_coverage_promotes_auth_pages_apis_files_and_role_tasks(self):
        raw = _model_plan()
        raw["information_architecture"]["global_navigation"] = [{
            "path": "/about", "label": "About", "audience": "PUBLIC",
        }]
        raw["roles_and_access"].update({
            "authentication_required": True, "signup": "open",
        })
        raw["api_contracts"] = [{
            "name": "list-products", "method": "GET", "path": "/api/products",
            "audience": "ROLE manager", "requirement_ids": ["REQ-001"],
        }]
        raw["tasks"][0]["actor"] = "ROLE manager"
        plan = PlannerAgent(None, "test-model").normalize(raw)

        routes = {route["path"]: route["file"] for route in plan["routes"]}
        self.assertEqual(routes["/about"], "app/about/page.jsx")
        self.assertEqual(routes["/sign-in"], "app/sign-in/page.jsx")
        self.assertEqual(routes["/sign-up"], "app/sign-up/page.jsx")
        self.assertEqual(routes["/api/products"], "app/api/products/route.js")
        files = {file["path"] for file in plan["file_plan"]}
        self.assertIn("app/sign-up/page.jsx", files)
        self.assertIn("app/api/products/route.js", files)
        assigned = {file["path"] for task in plan["tasks"]
                    for file in task["files"]}
        self.assertIn("app/sign-up/page.jsx", assigned)
        self.assertEqual(plan["tasks"][0]["actor"], "manager")

    def test_auth_roles_and_seed_contract_are_normalized_before_build(self):
        raw = _model_plan()
        raw["roles_and_access"].update({
            "authentication_required": True,
            "demo_accounts": [{
                "email": "admin@demo.local", "password": "password123",
                "role": "admin", "name": "Demo Admin",
            }],
        })
        raw["e2e_plan"]["journeys"][0]["actor"] = "ROLE admin"
        raw["capabilities"][0]["actor"] = "ROLE admin"
        plan = PlannerAgent(None, "test-model").normalize(raw)

        self.assertEqual(plan["e2e_plan"]["journeys"][0]["actor"], "admin")
        self.assertEqual(plan["capabilities"][0]["actor"], "admin")
        seed = next(file for file in plan["file_plan"]
                    if file["path"] == "lib/seed.js")
        self.assertIn("ensureDemoAccounts", " ".join(seed["contracts"]))

    def test_stream_parser_accepts_split_file_tags(self):
        events = []
        parser = FileStreamParser(
            lambda text: events.append(("text", text)),
            lambda path: events.append(("start", path)),
            lambda token: events.append(("token", token)),
            lambda path, body: events.append(("end", path, body)),
        )
        parser.feed("ready<write_")
        parser.feed('file path="app/page.jsx">export default 1</write_file>done')
        parser.close()

        self.assertIn(("start", "app/page.jsx"), events)
        self.assertIn(("end", "app/page.jsx", "export default 1"), events)
        self.assertTrue(any(event[0] == "text" and "ready" in event[1]
                            for event in events))

    def test_auth_client_import_is_not_mistaken_for_server_auth(self):
        from agents.core.ollama_client import OllamaClient
        from agents.planner.architecture import ArchitectAgent

        with tempfile.TemporaryDirectory() as tmp:
            arch = ArchitectAgent(OllamaClient(), "test-model", Path(tmp))
            arch.files = {
                "app/page.jsx": (
                    "'use client';\n"
                    "import { useSession } from '@/lib/auth-client';\n"
                    "export default function Page() { return null }\n"
                )
            }
            self.assertFalse(any("server/database" in error
                                 for error in arch.lint_generated()))

    def test_scaffold_defaults_cannot_be_overwritten_by_a_build_turn(self):
        from agents.core.ollama_client import OllamaClient
        from agents.planner.architecture import ArchitectAgent

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lib" / "auth.js"
            path.parent.mkdir(parents=True)
            path.write_text("export const safe = true\n", encoding="utf-8")
            arch = ArchitectAgent(OllamaClient(), "test-model", Path(tmp))
            arch.files["lib/auth.js"] = path.read_text(encoding="utf-8")

            self.assertFalse(arch.write_file("lib/auth.js", "broken"))
            self.assertEqual(path.read_text(encoding="utf-8"),
                             "export const safe = true\n")

    def test_unawaited_collection_access_is_a_lint_error(self):
        from agents.core.ollama_client import OllamaClient
        from agents.planner.architecture import ArchitectAgent

        with tempfile.TemporaryDirectory() as tmp:
            arch = ArchitectAgent(OllamaClient(), "test-model", Path(tmp))
            arch.plan = {"file_plan": [{"path": "app/page.jsx"}]}
            arch.files = {"app/page.jsx": (
                "export async function Page() {\n"
                "  const rooms = getCollection('rooms')\n"
                "  return rooms.find({})\n"
                "}\n"
            )}
            self.assertTrue(any("await async getCollection" in error
                                for error in arch.lint_generated()))

    def test_unawaited_dynamic_params_are_a_lint_error(self):
        from agents.core.ollama_client import OllamaClient
        from agents.planner.architecture import ArchitectAgent

        with tempfile.TemporaryDirectory() as tmp:
            arch = ArchitectAgent(OllamaClient(), "test-model", Path(tmp))
            path = "app/api/rooms/[id]/route.js"
            arch.plan = {"file_plan": [{"path": path}]}
            arch.files = {path: (
                "export async function GET(request, { params }) {\n"
                "  const { id } = params; return Response.json({ id })\n"
                "}\n"
            )}
            self.assertTrue(any("await Next.js dynamic-route params" in error
                                for error in arch.lint_generated()))

    def test_plain_mongo_demo_password_is_invalid_for_better_auth(self):
        from agents.core.ollama_client import OllamaClient
        from agents.planner.architecture import ArchitectAgent

        with tempfile.TemporaryDirectory() as tmp:
            arch = ArchitectAgent(OllamaClient(), "test-model", Path(tmp))
            arch.plan = {"file_plan": [{"path": "lib/seed.js"}]}
            arch.files = {
                "lib/auth.js": "export const auth = betterAuth({})\n",
                "lib/seed.js": (
                    "export async function seed() {\n"
                    "  await users.updateOne({ email: 'admin@demo.local' },\n"
                    "    { $setOnInsert: { password: 'password123' } })\n"
                    "}\n"
                ),
            }
            self.assertTrue(any("auth.api.signUpEmail" in error
                                for error in arch.lint_generated()))

    def test_analyzer_blocks_demo_rows_that_bypass_better_auth(self):
        from agents.analysis.analyzer import AnalyzerAgent
        from agents.core.ollama_client import OllamaClient
        from agents.planner.architecture import ArchitectAgent

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "lib").mkdir()
            (root / "lib" / "auth.js").write_text(
                "export const auth = betterAuth({})\n", encoding="utf-8")
            (root / "lib" / "seed.js").write_text(
                "await users.insertOne({ email: 'admin@demo.local', password: 'password123' })\n",
                encoding="utf-8")
            arch = ArchitectAgent(OllamaClient(), "test-model", root)
            arch.plan = {"demo_accounts": [{
                "email": "admin@demo.local", "password": "password123",
                "role": "admin",
            }]}
            findings = AnalyzerAgent(arch, root).better_auth_demo_seed()

            self.assertEqual([finding.code for finding in findings],
                             ["BETTER_AUTH_DEMO_SEED"])

    def test_e2e_account_resolution_accepts_role_access_prefix(self):
        from qa_agent.e2e.e2e_context import E2EContextMixin

        class Arch:
            project_dir = Path(".")
            plan = {"demo_accounts": [{
                "email": "admin@demo.local", "password": "password123",
                "role": "admin",
            }]}

        account = E2EContextMixin(Arch()).account_for("ROLE admin")
        self.assertEqual(account["email"], "admin@demo.local")


if __name__ == "__main__":
    unittest.main()
