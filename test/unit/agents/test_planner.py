"""Contracts for the unified LLM planner and its legacy QA views."""
from __future__ import annotations

import json
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import xml.etree.ElementTree as ET

from agents.planner.builder.app_builder import ArchitectAgent, FileStreamParser
from agents.planner.templates.runtime_defaults import render_templates
from agents.planner.planning.planner_agent import PlannerAgent, render_sitemap_xml


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
        "file_plan": [
            {"path": "app/layout.jsx", "kind": "server",
             "purpose": "Root shell wrapping every route in Navbar and Footer"},
            {"path": "components/Navbar.jsx", "kind": "client",
             "purpose": "Global navigation",
             "contracts": ["Global navigation: /, /products"]},
            {"path": "components/Footer.jsx", "kind": "server",
             "purpose": "Global footer"},
            {"path": "app/page.jsx", "purpose": "Overview"},
            {"path": "app/products/page.jsx", "purpose": "Inventory UI"},
        ],
        "tasks": [
            {"id": 0, "title": "App shell and global navigation",
             "goal": "Wrap every route in one shared shell",
             "files": ["app/layout.jsx", "components/Navbar.jsx",
                       "components/Footer.jsx"]},
            {"id": 1, "title": "Inventory", "goal": "Build inventory",
             "files": ["app/page.jsx", "app/products/page.jsx"],
             "requirement_ids": ["REQ-001"]},
        ],
        "dependencies": [],
        "definition_of_done": ["E2E journey passes"],
    }


class UnifiedPlannerTests(unittest.TestCase):
    def test_builder_keeps_project_memory_paths_after_mixin_refactors(self):
        self.assertEqual(ArchitectAgent.PLAN_JSON, ".agentforge/plan.json")
        self.assertEqual(ArchitectAgent.CONVO_JSON, ".agentforge/convo.json")

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
        self.assertIn("<sitemap", bundle.sitemap_xml)

    def test_the_planner_is_asked_again_until_nothing_is_missing(self):
        incomplete = _model_plan()
        incomplete["file_plan"] = [item for item in incomplete["file_plan"]
                                   if item["path"] != "app/page.jsx"]
        incomplete["tasks"][1]["files"] = ["app/products/page.jsx"]
        answers = [incomplete, _model_plan()]
        calls = []

        def stream(messages, on_delta, **_kwargs):
            calls.append(messages)
            on_delta(json.dumps(answers[min(len(calls) - 1, len(answers) - 1)]))

        planner = PlannerAgent(None, "test-model", stream=stream)
        bundle = planner.create("Managers can add products.")

        # One planning call, then exactly one gap round, then it is complete.
        self.assertEqual(len(calls), 2)
        self.assertIn("app/page.jsx", calls[1][-1]["content"])
        self.assertEqual(planner.plan_gaps(bundle.data), [])
        self.assertIn("app/page.jsx",
                      {file["path"] for file in bundle.data["file_plan"]})

    def test_a_truncated_gap_round_never_replaces_a_fuller_plan(self):
        """A retry that parses smaller than what we hold is discarded."""
        full = _model_plan()
        full["file_plan"] = [item for item in full["file_plan"]
                             if item["path"] != "app/page.jsx"]
        full["tasks"][1]["files"] = ["app/products/page.jsx"]
        truncated = {"project": {"name": "stock-desk", "title": "Stock Desk"}}
        answers = [full, truncated, truncated, truncated]
        calls = []

        def stream(messages, on_delta, **_kwargs):
            calls.append(messages)
            on_delta(json.dumps(answers[min(len(calls) - 1, len(answers) - 1)]))

        planner = PlannerAgent(None, "test-model", stream=stream)
        bundle = planner.create("Managers can add products.")

        # The plan survives, and the loop stops instead of burning more rounds.
        self.assertIsNotNone(bundle)
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(bundle.data["routes"]), 2)
        self.assertTrue(bundle.data["file_plan"])

    def test_an_empty_plan_is_refused_rather_than_built(self):
        """No routes and no files is a failed answer, not a small product."""
        def stream(_messages, on_delta, **_kwargs):
            on_delta(json.dumps({"project": {"name": "x", "title": "X"}}))

        planner = PlannerAgent(None, "test-model", stream=stream)
        self.assertIsNone(planner.create("Managers can add products."))

    def test_a_complete_first_answer_costs_only_one_call(self):
        calls = []

        def stream(messages, on_delta, **_kwargs):
            calls.append(messages)
            on_delta(json.dumps(_model_plan()))

        planner = PlannerAgent(None, "test-model", stream=stream)
        bundle = planner.create("Managers can add products.")

        self.assertEqual(len(calls), 1)
        self.assertEqual(planner.plan_gaps(bundle.data), [])

    def test_site_map_is_one_xml_document_every_build_round_carries(self):
        raw = _model_plan()
        raw["information_architecture"]["global_navigation"] = [
            {"audience": "PUBLIC", "label": "Products & stock", "path": "/products",
             "test_id": "nav-products"}]
        raw["routes"][1]["layout"] = "Filter bar over a two-column grid"
        raw["api_contracts"] = [{
            "name": "list-products", "method": "GET", "path": "/api/products",
            "handler_file": "app/api/products/route.js",
            "called_from": ["app/products/page.jsx"],
            "success_effect": "The grid renders every product"}]
        plan = PlannerAgent(None, "test-model").normalize(raw)

        root = ET.fromstring(render_sitemap_xml(plan))
        pages = {page.get("path"): page for page in root.findall("page")}
        self.assertEqual(pages["/products"].get("file"), "app/products/page.jsx")
        self.assertEqual(pages["/products"].findtext("layout"),
                         "Filter bar over a two-column grid")
        self.assertEqual(root.find("navigation/link").get("label"),
                         "Products & stock")
        self.assertEqual(root.find("api").get("path"), "/api/products")

        with tempfile.TemporaryDirectory() as folder:
            arch = ArchitectAgent(None, "test-model", Path(folder), {}, stack="next")
            self.assertEqual(arch._sitemap_block(), "")
            arch.plan = plan
            block = arch._sitemap_block()
            self.assertIn("APPROVED SITE MAP", block)
            self.assertIn("<page path=\"/products\"", block)

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

    def test_database_clients_recover_instead_of_caching_a_dead_one(self):
        raw = _model_plan()
        raw["roles_and_access"]["authentication_required"] = True
        plan = PlannerAgent(None, "test-model").normalize(raw)
        files = render_templates("next", plan, mongo_uri="mongodb://127.0.0.1:27017/test",
                                 db_name="test", dev_port=3000)

        mongodb = files["lib/mongodb.js"]
        self.assertIn("cache(undefined)", mongodb)
        self.assertIn("serverSelectionTimeoutMS", mongodb)
        auth = files["lib/auth.js"]
        self.assertIn("Topology is closed", auth)
        self.assertIn("export let auth", auth)
        self.assertIn("live(createDemoAccounts)", auth)
        route = files["app/api/auth/[...all]/route.js"]
        self.assertIn("ensureDemoAccounts().catch", route)
        self.assertNotIn("let handlers", route)

    def test_an_unreachable_database_is_never_reported_as_available(self):
        from agents.data import mongo_lifecycle

        manager = mongo_lifecycle.MongoManager()
        with unittest.mock.patch.object(mongo_lifecycle, "get_uri_override",
                                        return_value="mongodb://127.0.0.1:1/x"):
            self.assertFalse(manager.reachable(timeout=0.3))
            self.assertFalse(manager.ensure_running())
        self.assertFalse(manager.available)
        self.assertTrue(manager.reason)

    def test_role_actors_are_normalized_without_authoring_plan_content(self):
        raw = _model_plan()
        raw["tasks"][1]["actor"] = "ROLE manager"
        plan = PlannerAgent(None, "test-model").normalize(raw)

        actors = {task["title"]: task["actor"] for task in plan["tasks"]}
        self.assertEqual(actors["Inventory"], "manager")

    def test_every_dangling_reference_is_reported_as_a_gap(self):
        raw = _model_plan()
        raw["information_architecture"]["global_navigation"] = [{
            "path": "/about", "label": "About", "audience": "PUBLIC",
        }]
        raw["roles_and_access"].update({
            "authentication_required": True, "signup": "open",
        })
        raw["api_contracts"] = [{
            "name": "list-products", "method": "GET", "path": "/api/products",
            "handler_file": "app/api/products/route.js",
            "requirement_ids": ["REQ-001"],
        }]
        planner = PlannerAgent(None, "test-model")
        plan = planner.normalize(raw)

        # Nothing was invented to paper over the holes …
        self.assertNotIn("/about", {page["path"] for page in plan["site_map"]})
        self.assertNotIn("app/api/products/route.js",
                         {file["path"] for file in plan["file_plan"]})
        # … every one of them is reported back to the planner instead.
        gaps = "\n".join(planner.plan_gaps(plan))
        self.assertIn("/about", gaps)
        self.assertIn("app/api/products/route.js", gaps)
        self.assertIn("sign-in", gaps)
        self.assertIn("sign-up", gaps)

    def test_planner_owns_its_account_flows(self):
        """The planner's own auth paths survive, and none are invented."""
        raw = _model_plan()
        raw["roles_and_access"].update({
            "authentication_required": True, "signup": "open",
        })
        raw["site_map"] += [
            {"path": "/login", "parent": "/", "label": "Log in", "type": "page"},
            {"path": "/signup", "parent": "/", "label": "Sign up", "type": "page"},
        ]
        plan = PlannerAgent(None, "test-model").normalize(raw)
        served = {page["path"] for page in plan["site_map"]}

        self.assertIn("/login", served)
        self.assertIn("/signup", served)
        # No rival twin for a flow the plan already serves.
        self.assertNotIn("/sign-in", served)
        self.assertNotIn("/sign-up", served)

    def test_planner_never_invents_a_missing_account_flow(self):
        """A dropped sign-in page stays dropped; the analyzer owns that gap."""
        raw = _model_plan()
        raw["roles_and_access"].update({
            "authentication_required": True, "signup": "open",
        })
        plan = PlannerAgent(None, "test-model").normalize(raw)
        served = {page["path"] for page in plan["site_map"]}

        self.assertFalse(served & {"/sign-in", "/signin", "/login"})
        self.assertFalse(served & {"/sign-up", "/signup", "/register"})

    def test_scaffold_placeholders_can_always_be_replaced(self):
        """The 'Building…' page and the stub seed must never lock themselves in.

        They ship only so the app compiles before the product exists. When the
        plan does not name them, the old guard refused every later write and
        the app served the placeholder forever.
        """
        with tempfile.TemporaryDirectory() as tmp:
            arch = ArchitectAgent(None, "test-model", Path(tmp))
            arch.plan = {"file_plan": []}          # nothing names these paths

            for rel in ("app/page.jsx", "lib/seed.js"):
                self.assertTrue(arch.write_file(rel, "export default function P(){}\n"),
                                f"{rel} must stay replaceable")
            for rel in ("lib/mongodb.js", "package.json"):
                self.assertFalse(arch.write_file(rel, "broken\n"),
                                 f"{rel} must stay protected")

    def test_the_planners_own_shell_survives_normalization(self):
        plan = PlannerAgent(None, "test-model").normalize(_model_plan())

        files = {file["path"] for file in plan["file_plan"]}
        self.assertLessEqual({"app/layout.jsx", "components/Navbar.jsx",
                              "components/Footer.jsx"}, files)
        first = plan["tasks"][0]
        self.assertEqual(first["title"], "App shell and global navigation")
        self.assertEqual({file["path"] for file in first["files"]},
                         {"app/layout.jsx", "components/Navbar.jsx",
                          "components/Footer.jsx"})
        navbar = next(file for file in plan["file_plan"]
                      if file["path"] == "components/Navbar.jsx")
        self.assertIn("/products", "".join(navbar["contracts"]))

    def test_a_missing_shell_is_a_gap_not_a_python_injection(self):
        raw = _model_plan()
        raw["file_plan"] = [item for item in raw["file_plan"]
                            if not item["path"].startswith(("app/layout",
                                                            "components/"))]
        raw["tasks"] = [raw["tasks"][1]]
        planner = PlannerAgent(None, "test-model")
        plan = planner.normalize(raw)

        files = {file["path"] for file in plan["file_plan"]}
        self.assertNotIn("app/layout.jsx", files)
        gaps = "\n".join(planner.plan_gaps(plan))
        self.assertIn("app/layout.jsx", gaps)
        self.assertIn("components/Navbar.jsx", gaps)

    def test_page_layout_reaches_the_builder_with_its_file(self):
        raw = _model_plan()
        raw["routes"][1]["layout"] = ("Shell content column: filter bar, then a "
                                      "two-column grid, then the create form")
        plan = PlannerAgent(None, "test-model").normalize(raw)

        page = next(file for file in plan["file_plan"]
                    if file["path"] == "app/products/page.jsx")
        self.assertIn("two-column grid", page["layout"])
        self.assertIn("two-column grid",
                      PlannerAgent(None, "test-model").render_markdown(plan))

    def test_pictures_are_planned_only_when_the_request_asks_for_them(self):
        raw = _model_plan()
        raw["data_model"] = [{
            "collection": "products", "purpose": "Sellable stock",
            "fields": [{"name": "name", "type": "string"}],
            "seed": {"count": 2, "identity_field": "name"},
        }]
        planner = PlannerAgent(None, "test-model")

        quiet = planner.normalize(json.loads(json.dumps(raw)),
                                  "Managers can add products.")
        self.assertEqual(quiet["images"], [])
        self.assertEqual([field["name"] for field in
                          quiet["data_model"][0]["fields"]], ["name"])

        asked = planner.normalize(json.loads(json.dumps(raw)),
                                  "Managers can add products with a pic each.")
        keys = [image["key"] for image in asked["images"]]
        self.assertEqual(keys[:2], ["banner", "poster"])
        self.assertIn("products-1", keys)
        self.assertIn("products-2", keys)
        self.assertIn("image", [field["name"] for field in
                                asked["data_model"][0]["fields"]])
        seeded = next(image for image in asked["images"]
                      if image["key"] == "products-1")
        self.assertIn("/generated/products-1.png", seeded["purpose"])

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
        planner = PlannerAgent(None, "test-model")
        plan = planner.normalize(raw)

        self.assertEqual(plan["e2e_plan"]["journeys"][0]["actor"], "admin")
        self.assertEqual(plan["capabilities"][0]["actor"], "admin")
        # The seed file is the planner's to write, so its absence is a gap.
        self.assertNotIn("lib/seed.js",
                         {file["path"] for file in plan["file_plan"]})
        self.assertIn("lib/seed.js", "\n".join(planner.plan_gaps(plan)))

    def test_a_scalar_answer_is_kept_as_a_one_item_list(self):
        """`"exports": "ensureSeeded"` means the list — dropping it hung the loop.

        The gap round asked for exactly that value, normalization threw the
        scalar away, and the same gap was reported until the rounds ran out.
        """
        raw = _model_plan()
        raw["roles_and_access"]["demo_accounts"] = [{
            "email": "a@demo.local", "password": "password123", "role": "admin",
        }]
        raw["file_plan"].append({"path": "lib/seed.js", "kind": "server",
                                 "purpose": "Seed demo rows and accounts",
                                 "exports": "ensureSeeded"})   # scalar, not a list
        raw["tasks"][1]["files"].append("lib/seed.js")
        planner = PlannerAgent(None, "test-model")

        plan = planner.normalize(raw)
        seed = next(f for f in plan["file_plan"] if f["path"] == "lib/seed.js")
        self.assertEqual(seed["exports"], ["ensureSeeded"])
        self.assertNotIn("ensureSeeded", "\n".join(planner.plan_gaps(plan)))

    def test_a_planned_seed_must_export_the_name_agentforge_calls(self):
        raw = _model_plan()
        raw["roles_and_access"].update({
            "authentication_required": True,
            "demo_accounts": [{
                "email": "admin@demo.local", "password": "password123",
                "role": "admin", "name": "Demo Admin",
            }],
        })
        raw["file_plan"].append({"path": "lib/seed.js", "kind": "server",
                                 "purpose": "Seed demo rows and accounts"})
        raw["tasks"][1]["files"].append("lib/seed.js")
        planner = PlannerAgent(None, "test-model")

        gaps = "\n".join(planner.plan_gaps(planner.normalize(raw)))
        self.assertIn("ensureSeeded", gaps)

        raw["file_plan"][-1]["exports"] = ["ensureSeeded"]
        self.assertNotIn("ensureSeeded",
                         "\n".join(planner.plan_gaps(planner.normalize(raw))))

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
        from agents.core.llm.llm_client import OllamaClient
        from agents.planner.builder.app_builder import ArchitectAgent

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
        from agents.core.llm.llm_client import OllamaClient
        from agents.planner.builder.app_builder import ArchitectAgent

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
        from agents.core.llm.llm_client import OllamaClient
        from agents.planner.builder.app_builder import ArchitectAgent

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
        from agents.core.llm.llm_client import OllamaClient
        from agents.planner.builder.app_builder import ArchitectAgent

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
        from agents.core.llm.llm_client import OllamaClient
        from agents.planner.builder.app_builder import ArchitectAgent

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
        from agents.core.llm.llm_client import OllamaClient
        from agents.planner.builder.app_builder import ArchitectAgent

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
